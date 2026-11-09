"""Match observed native versions to source references without guessing by filename."""
import argparse
import json
from pathlib import Path
import re


DEFAULT_LOCK = Path(__file__).resolve().parents[1] / 'third_party/native-source-lock.json'


def ffprobe_external_versions(application):
    rows = []
    for path in Path(application).glob('_internal/tools/ffprobe/*'):
        if not path.is_file() or 'readme' not in path.name.lower():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        marker = "external libraries' versions:"
        if marker not in text:
            continue
        for line in text.split(marker, 1)[1].splitlines():
            match = re.match(r'^([A-Za-z0-9_-]+)\s+([^\s].*)$', line.strip())
            if match:
                rows.append({'name': match.group(1), 'reported_version': match.group(2),
                             'evidence': path.relative_to(application).as_posix(),
                             'status': 'version-reported-source-build-match-open'})
    return rows


def review_native_dependencies(application, lock_path=DEFAULT_LOCK):
    application = Path(application)
    inventory = json.loads((application / 'distribution-inventory.json').read_text(encoding='utf-8'))
    lock = json.loads(Path(lock_path).read_text(encoding='utf-8'))
    sources = {row['id']: row for row in lock['sources']}
    files = {row['path']: row for row in inventory['files']}
    config_path = application / 'upstream-build-info/perl-build-configuration.txt'
    config = config_path.read_text(encoding='utf-8') if config_path.exists() else ''
    perl = re.search(r'revision (\d+) version (\d+) subversion (\d+)', config)
    gcc = re.search(r"gccversion='([^']+)'", config)
    origin_path = application / 'binary-origins.json'
    origins = {row['path']: row for row in json.loads(origin_path.read_text(encoding='utf-8'))['files']} if origin_path.exists() else {}
    matches = []
    for relative, entry in files.items():
        if not relative.lower().endswith(('.dll', '.pyd')):
            continue
        name = relative.rsplit('/', 1)[-1].lower()
        version_info = entry.get('pe_version') or {}
        version = version_info.get('ProductVersion') or version_info.get('FileVersion')
        source_id = None
        evidence = None
        if name.startswith(('libssl-', 'libcrypto-')) and version:
            source_id, evidence = 'openssl-' + version, 'Windows PE version metadata'
        elif name.startswith('liblzma-') and version:
            source_id, evidence = 'xz-' + version, 'Windows PE version metadata'
        elif name == 'perl532.dll' and perl:
            tool = files.get('_internal/tools/exiftool/exiftool_files/perl532.dll')
            if tool and tool['sha256'] == entry['sha256']:
                version = '.'.join(perl.groups())
                source_id, evidence = 'perl-' + version, 'Perl -V and exact byte match to the staged Perl runtime'
        elif name in ('libgcc_s_seh-1.dll', 'libstdc++-6.dll') and gcc:
            tool = files.get('_internal/tools/exiftool/exiftool_files/' + name)
            if tool and tool['sha256'] == entry['sha256']:
                version = gcc.group(1)
                source_id, evidence = 'gcc-' + version, 'Compiler identified by Perl -V; exact byte match to staged runtime (provider patches still require matching)'
            else:
                evidence = 'Different bytes from staged Perl runtime; do not assign its compiler version to this DLL'
        elif name == 'libwinpthread-1.dll':
            tool = files.get('_internal/tools/exiftool/exiftool_files/' + name)
            info_paths = list(application.glob('licenses/upstream/**/gcc-toolchain/_INFO_'))
            runtime_info = '\n'.join(path.read_text(encoding='utf-8', errors='replace') for path in info_paths)
            runtime_version = re.search(r'Package:\s*mingw-w64-crt-v([^\s]+)', runtime_info)
            if tool and tool['sha256'] == entry['sha256'] and runtime_version:
                version = runtime_version.group(1)
                source_id, evidence = 'mingw-w64-' + version, 'Preserved upstream runtime notice and exact byte match to staged runtime'
        elif name.startswith(('vcruntime', 'msvcp', 'api-ms-')) or name == 'ucrtbase.dll':
            matches.append({'path': relative, 'sha256': entry['sha256'], 'version': version,
                'status': 'redistribution-terms-review',
                'evidence': 'Microsoft runtime; apply its redistribution terms, not an invented open-source license',
                'terms_url': 'https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution'})
            continue
        else:
            continue
        match = {'path': relative, 'sha256': entry['sha256'], 'version': version,
                 'evidence': evidence or 'No reliable version evidence', 'status': 'source-reference-unresolved'}
        if relative in origins:
            match['build_origin'] = origins[relative]
        if source_id in sources:
            match.update(source_id=source_id, source=sources[source_id], status='version-reference-matched-build-review-open')
        matches.append(match)
    for fingerprint in lock.get('fingerprints', []):
        entry = files.get(fingerprint['path'])
        if entry:
            matches.append(dict(fingerprint, observed_sha256=entry['sha256'],
                status=fingerprint['status'] if entry['sha256'] == fingerprint['sha256'] else 'fingerprint-changed-needs-identification'))
    notices = []
    for path in application.glob('licenses/upstream/**/_INFO_'):
        text = path.read_text(encoding='utf-8', errors='replace')
        for reported in re.findall(r'(?im)^Package:\s*(openssl-[^\s]+)', text):
            actual = sorted({m['version'] for m in matches if m.get('source_id', '').startswith('openssl-')})
            if actual and reported.removeprefix('openssl-') not in actual:
                notices.append({'path': path.relative_to(application).as_posix(), 'reported_package': reported,
                    'observed_openssl_versions': actual, 'status': 'historical-notice-does-not-identify-current-openssl-dlls'})
    report = {'schema_version': 1, 'commit': inventory['commit'], 'public_distribution_approved': False,
              'matches': matches, 'notice_mismatches': notices,
              'ffprobe_external_libraries': ffprobe_external_versions(application),
              'scope': 'Version/source evidence only. This does not certify binary correspondence or license compliance.'}
    (application / 'native-dependency-review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--application', type=Path, default=Path('dist/PremiereTimelinePrep'))
    parser.add_argument('--lock', type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()
    result = review_native_dependencies(args.application, args.lock)
    print('Native evidence rows:', len(result['matches']), 'historical notice mismatches:', len(result['notice_mismatches']))
