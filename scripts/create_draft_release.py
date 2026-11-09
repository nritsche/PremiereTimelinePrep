"""Prepare a draft release from a tested artifact and reviewed source bundle.

Run only through the manual release workflow. Publishing remains a maintainer step.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_review(source, commit, inventory_hash, expected_components):
    import zipfile
    with zipfile.ZipFile(source) as materials:
        try:
            source_review = json.loads(materials.read('distribution-review.json'))
        except KeyError as exc:
            raise ValueError('Corresponding-source ZIP must include a completed distribution-review.json') from exc
        if source_review.get('public_distribution_approved') is not True or source_review.get('commit') != commit:
            raise ValueError('Source/license review is incomplete or belongs to a different build')
        if source_review.get('distribution_inventory_sha256') != inventory_hash:
            raise ValueError('Source review must identify the exact distribution inventory')
        reviewed = source_review.get('components', [])
        if {item.get('id') for item in reviewed} != expected_components or any(item.get('status') != 'reviewed' for item in reviewed):
            raise ValueError('Every inventoried component group needs a completed review')
        for item in reviewed:
            if not item.get('rationale') or not item.get('license_materials'):
                raise ValueError('Each component review must identify its license materials and rationale')
            for material in item['license_materials'] + item.get('source_materials', []):
                member = material.get('path', '')
                if not member or member.startswith('/') or '..' in Path(member).parts:
                    raise ValueError('Invalid source material path')
                if hashlib.sha256(materials.read(member)).hexdigest() != material.get('sha256'):
                    raise ValueError('Source material checksum mismatch')


def main():
    version, run_id = os.environ['RELEASE_VERSION'], os.environ['BUILD_RUN_ID']
    source_url, expected = os.environ['SOURCE_BUNDLE_URL'], os.environ['SOURCE_BUNDLE_SHA256'].lower()
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', version) or not run_id.isdigit():
        raise ValueError('Use a version such as v0.1.0-alpha.1 and a numeric workflow run ID')
    if not source_url.startswith('https://') or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Provide an HTTPS corresponding-source ZIP URL and its SHA-256')
    if os.environ.get('COMPLIANCE_REVIEWED') != 'true':
        raise ValueError('Complete the distribution review before creating a release')
    if not Path('LICENSE').is_file():
        raise ValueError('Choose and commit the project license first')
    run = json.loads(subprocess.check_output(['gh', 'run', 'view', run_id, '--json',
        'conclusion,event,headSha,workflowName'], text=True))
    if run.get('conclusion') != 'success' or run.get('event') not in ('push', 'workflow_dispatch') or run.get('workflowName') != 'Build Windows executable':
        raise ValueError('Use a successful trusted Windows build, not a pull-request artifact')
    staging = Path('release-staging')
    staging.mkdir(exist_ok=False)
    artifact = staging / 'windows'
    subprocess.run(['gh', 'run', 'download', run_id, '--name', 'PremiereTimelinePrep-windows-x64', '--dir', str(artifact)], check=True)
    manifest = json.loads((artifact / 'build-manifest.json').read_text(encoding='utf-8'))
    test = json.loads((artifact / 'self-test.json').read_text(encoding='utf-8'))
    executable = artifact / 'PremiereTimelinePrep.exe'
    if test.get('success') is not True or file_hash(executable) != manifest.get('executable_sha256'):
        raise ValueError('Artifact self-test or executable hash failed')
    inventory_path = artifact / 'distribution-inventory.json'
    if not inventory_path.is_file() or file_hash(inventory_path) != manifest.get('distribution_inventory_sha256'):
        raise ValueError('Artifact must contain the recorded full distribution inventory')
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    for entry in inventory['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or ':' in entry['path'] or "\\" in entry['path']:
            raise ValueError('Unsafe inventory path')
        path = artifact / relative
        if not path.is_file() or file_hash(path) != entry['sha256']:
            raise ValueError('Distribution inventory mismatch: ' + entry['path'])
    if not (artifact / 'LICENSE').is_file():
        raise ValueError('Rebuild the executable from a commit containing the project license')
    if not any(p.is_file() and p.name != 'README.md' for p in (artifact / 'licenses').rglob('*')):
        raise ValueError('Artifact does not contain reviewed upstream license texts')
    commit = manifest['commit']
    if commit != run.get('headSha'):
        raise ValueError('Artifact commit does not match the trusted workflow run')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid artifact commit')
    subprocess.run(['git', 'cat-file', '-e', commit + '^{commit}'], check=True)
    source = staging / (version + '-corresponding-source.zip')
    with urllib.request.urlopen(source_url, timeout=120) as response, source.open('wb') as stream:
        if not response.url.startswith('https://'):
            raise ValueError('Source URL redirected away from HTTPS')
        shutil.copyfileobj(response, stream)
    if file_hash(source) != expected:
        raise ValueError('Corresponding-source checksum mismatch')
    import zipfile
    if not zipfile.is_zipfile(source):
        raise ValueError('Corresponding-source bundle must be a ZIP')
    expected_components = {item['id'] for item in json.loads((artifact / 'distribution-review.json').read_text(encoding='utf-8'))['components']}
    validate_source_review(source, commit, manifest['distribution_inventory_sha256'], expected_components)
    application_source = staging / (version + '-application-source.zip')
    subprocess.run(['git', 'archive', '--format=zip', '--output', str(application_source), commit], check=True)
    archive = Path(shutil.make_archive(str(staging / (version + '-windows-x64')), 'zip', artifact))
    assets = [archive, source, application_source]
    sums = staging / 'SHA256SUMS.txt'
    sums.write_text(''.join('{}  {}\n'.format(file_hash(path), path.name) for path in assets), encoding='utf-8')
    notes = staging / 'release-notes.md'
    notes.write_text('Experimental Windows build from commit {}.\n\n'
        'XML export requires Premiere import validation. Review the included limitations and third-party notices. '
        'The download includes a build manifest, packaged self-test results, and checksums. '
        'Corresponding-source materials were supplied and reviewed by the release maintainer.\n'.format(commit), encoding='utf-8')
    subprocess.run(['gh', 'release', 'create', version, '--draft', '--prerelease', '--target', commit,
                    '--title', 'Premiere Timeline Prep ' + version, '--notes-file', str(notes),
                    *map(str, assets), str(sums)], check=True)


if __name__ == '__main__':
    main()
