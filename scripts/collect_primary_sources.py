"""Collect exact primary upstream source candidates for a PRIVATE review build.

These archives are evidence, not a complete corresponding-source approval:
compiler/runtime dependencies and provider build configuration still need review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import tarfile
from pathlib import PurePosixPath


SOURCES = [
    ('python-3.12.10.tar.xz', 'https://www.python.org/ftp/python/3.12.10/Python-3.12.10.tar.xz'),
    ('qtbase-6.12.0.tar.xz', 'https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz'),
    ('qtsvg-6.12.0.tar.xz', 'https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtsvg-everywhere-src-6.12.0.tar.xz'),
    ('qtimageformats-6.12.0.tar.xz', 'https://download.qt.io/archive/qt/6.12/6.12.0/submodules/qtimageformats-everywhere-src-6.12.0.tar.xz'),
    ('pyside-shiboken-6.12.0.tar.xz', 'https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz'),
    ('ffmpeg-946fcce07b6dcd0331c8cc609192aeff5e1924f8.tar.gz', 'https://api.github.com/repos/FFmpeg/FFmpeg/tarball/946fcce07b6dcd0331c8cc609192aeff5e1924f8'),
    ('exiftool-2200871d9cef988051d2a99d67df3bda6cbb30a8.tar.gz', 'https://api.github.com/repos/exiftool/exiftool/tarball/2200871d9cef988051d2a99d67df3bda6cbb30a8'),
]


# Observed in the successful private source-review build 42621680460.
# These pin candidate archive bytes; they do not establish legal correspondence.
EXPECTED_SHA256 = {
    'python-3.12.10.tar.xz': '07ab697474595e06f06647417d3c7fa97ded07afc1a7e4454c5639919b46eaea',
    'qtbase-6.12.0.tar.xz': 'a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307',
    'qtsvg-6.12.0.tar.xz': 'e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331',
    'qtimageformats-6.12.0.tar.xz': '0943132b5db8de6b6a7f1d162682173e8763c7ed94e80fd39113292845f67762',
    'pyside-shiboken-6.12.0.tar.xz': '099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751',
    'ffmpeg-946fcce07b6dcd0331c8cc609192aeff5e1924f8.tar.gz': 'c8a74e6eff0d38850403ee8eff3a95721984b45a3cd25f92b8905886571fc1be',
    'exiftool-2200871d9cef988051d2a99d67df3bda6cbb30a8.tar.gz': '0c1c0e2b9a7bb278ce3b2cad1654ac08f868a2b3c7ba95e7a4b12e4364db3069',
}


def extract_source_notices(archive, destination):
    """Copy source-shipped license/attribution files without extracting code."""
    copied = 0
    with tarfile.open(archive, 'r:*') as source:
        for member in source:
            if not member.isfile():
                continue
            relative = PurePosixPath(member.name.replace("\\", "/"))
            if relative.is_absolute() or '..' in relative.parts or any(':' in part for part in relative.parts):
                raise ValueError('Unsafe source archive path')
            name = relative.name.lower()
            if not (any(part.lower() in ('licenses', 'licences') for part in relative.parts) or any(word in name for word in ('license', 'licence', 'copying', 'copyright', 'notice')) or name in ('qt_attribution.json', 'reuse.toml')):
                continue
            if member.size > 4 * 1024 * 1024:
                continue
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.extractfile(member).read())
            copied += 1
    return copied


def collect(application, destination):
    manifest = json.loads((application / 'build-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('qt_version') != '6.12.0':
        raise ValueError('Update exact Qt library source versions for this build')
    if not manifest['python'].startswith('3.12.10 '):
        raise ValueError('Update the reviewed Python source URL for this build version')
    packages = {name.lower().replace('_', '-'): value for name, value in manifest['packages'].items()}
    if packages.get('pyside6-essentials') != '6.12.0' or packages.get('shiboken6') != '6.12.0':
        raise ValueError('Update the reviewed Qt/PySide source URLs for this build version')
    if '9.0.2-' not in manifest['tools']['ffprobe'] or manifest['tools']['exiftool'] != '13.59':
        raise ValueError('Update exact media-tool source revisions for this build version')
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for filename, url in SOURCES:
        path = destination / filename
        request = urllib.request.Request(url, headers={'User-Agent': 'PremiereTimelinePrep-source-review'})
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=120) as response, path.open('wb') as stream:
                if not response.url.startswith('https://'):
                    raise ValueError('Source download redirected away from HTTPS')
                total = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    total += len(chunk)
                    if total > 512 * 1024 * 1024:
                        raise ValueError('Source archive exceeds review download limit')
                    digest.update(chunk)
                    stream.write(chunk)
                resolved = response.url
                content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type or total < 1024:
                raise ValueError('Expected a source archive, received an error page or empty response')
            if digest.hexdigest() != EXPECTED_SHA256[filename]:
                raise ValueError('Source archive changed from the recorded review hash')
            row = {'filename': filename, 'url': url, 'resolved_url': resolved,
                   'sha256': digest.hexdigest(), 'size': total, 'status': 'downloaded-needs-correspondence-review'}
            # Keep upstream terms and attribution files beside the portable app.
            notice_root = application / 'licenses' / 'upstream-source-notices' / filename.replace('.tar.xz', '').replace('.tar.gz', '')
            row['notice_files_preserved'] = extract_source_notices(path, notice_root)
            print('Collected', filename, row['sha256'], flush=True)
        except Exception as exc:
            path.unlink(missing_ok=True)
            row = {'filename': filename, 'url': url, 'status': 'unavailable', 'error': str(exc)}
            print('Source unavailable:', filename, str(exc), flush=True)
        rows.append(row)
    report = {'commit': manifest['commit'], 'public_distribution_approved': False, 'sources': rows,
              'warning': 'Primary sources only. This is not a complete corresponding-source package. Match dependencies and exact provider build materials before approval.'}
    (destination / 'primary-source-index.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (destination / 'SHA256SUMS.txt').write_text(''.join('{}  {}\n'.format(row['sha256'], row['filename']) for row in rows if 'sha256' in row), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--application', type=Path, default=Path('dist/PremiereTimelinePrep'))
    parser.add_argument('--out', type=Path, default=Path('build-tools/primary-sources'))
    arguments = parser.parse_args()
    collect(arguments.application, arguments.out)
    from collect_native_sources import collect_native_sources
    collect_native_sources(arguments.application, arguments.out / 'native')
    # Added notices change the inventory, never the program or test results.
    from distribution_audit import audit_distribution, sha256
    manifest_path = arguments.application / 'build-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    audit_distribution(arguments.application, manifest['commit'])
    manifest['distribution_inventory_sha256'] = sha256(arguments.application / 'distribution-inventory.json')
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
