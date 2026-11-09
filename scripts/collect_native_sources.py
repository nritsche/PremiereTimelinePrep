"""Collect source candidates matched to the actual native version evidence."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request


def collect_native_sources(application, destination, lock_path=None):
    from native_dependency_review import DEFAULT_LOCK, review_native_dependencies
    from collect_primary_sources import extract_source_notices
    lock_path = Path(lock_path or DEFAULT_LOCK)
    review = review_native_dependencies(application, lock_path)
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    sources = {row['id']: row for row in lock['sources']}
    required = {row['source_id'] for row in review['matches'] if row.get('source_id')}
    for row in review['matches']:
        if row.get('status') == 'version-identified-build-correspondence-open':
            required.update(row.get('source_ids', []))
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for source_id in sorted(required):
        source = sources[source_id]
        if not re.fullmatch(r'[a-z0-9.-]+', source_id):
            raise ValueError('Unsafe source identifier')
        url = source['source_url']
        if not url.startswith('https://'):
            raise ValueError('Native source URL must use HTTPS')
        if 'api.github.com' in url and (not re.fullmatch(r'[0-9a-f]{40}', source.get('commit', '')) or not url.endswith('/' + source['commit'])):
            raise ValueError('GitHub source reference must identify an immutable commit')
        filename = source_id + ('.tar.xz' if source.get('archive_format') == 'tar.xz' else '.tar.gz')
        target = destination / filename
        row = {'id': source_id, 'filename': filename, 'url': url,
               'status': 'unavailable', 'match_scope': source.get('match_scope')}
        try:
            digest = hashlib.sha256()
            request = urllib.request.Request(url, headers={'User-Agent': 'PremiereTimelinePrep-native-review'})
            with urllib.request.urlopen(request, timeout=120) as response, target.open('wb') as stream:
                if not response.url.startswith('https://'):
                    raise ValueError('Native source redirected away from HTTPS')
                size = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    size += len(chunk)
                    if size > 512 * 1024 * 1024:
                        raise ValueError('Native source exceeds 512 MB limit')
                    stream.write(chunk)
                    digest.update(chunk)
            if source.get('archive_sha256') and digest.hexdigest() != source['archive_sha256']:
                raise ValueError('Native archive changed from its recorded review hash')
            notices = application / 'licenses' / 'native-source-notices' / source_id
            count = extract_source_notices(target, notices)
            row.update(status='source-candidate-collected-build-correspondence-open',
                       sha256=digest.hexdigest(), size=size, notices_preserved=count)
            print('Native source collected:', source_id, row['sha256'], flush=True)
        except Exception as exc:
            target.unlink(missing_ok=True)
            row['error'] = str(exc)
            print('Native source unavailable:', source_id, str(exc), flush=True)
        rows.append(row)
    result = {'commit': review['commit'], 'public_distribution_approved': False, 'sources': rows,
              'unresolved_files': [row['path'] for row in review['matches'] if row['status'] in ('source-reference-unresolved', 'fingerprint-changed-needs-identification')],
              'notice_mismatches': review['notice_mismatches'],
              'scope': 'Includes exact-version upstream source candidates; does not establish provider patch/build correspondence.'}
    (destination / 'native-source-index.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (destination / 'NATIVE-SHA256SUMS.txt').write_text(''.join('{}  {}\n'.format(row['sha256'], row['filename']) for row in rows if 'sha256' in row), encoding='utf-8')
    (application / 'native-source-index.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
