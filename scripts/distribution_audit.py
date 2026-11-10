"""Inventory a portable application and preserve actual upstream notices.

This records evidence for a distribution review; it does not infer that a DLL's
license obligations have been met from its name or a generic license text.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _is_notice(name):
    value = name.lower()
    return any(word in value for word in ('license', 'licence', 'copying', 'copyright', 'notice', 'authors', 'readme'))


def extract_notice_zip(archive, destination):
    """Extract the upstream notice collection, refusing paths outside its folder."""
    destination = Path(destination)
    count = 0
    with zipfile.ZipFile(archive) as package:
        if sum(member.file_size for member in package.infolist()) > 64 * 1024 * 1024:
            raise ValueError('Upstream notice archive exceeds 64 MB')
        for member in package.infolist():
            path = PurePosixPath(member.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or any(':' in part for part in path.parts):
                raise ValueError('Unsafe path in upstream notice archive')
            target = destination.joinpath(*path.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package.read(member))
                count += 1
    return count


def collect_notices(application):
    application = Path(application)
    destination = application / 'licenses' / 'upstream'
    copied = []
    internal = application / '_internal'
    for source in sorted(internal.rglob('*')):
        if not source.is_file() or not _is_notice(source.name):
            continue
        relative = source.relative_to(internal)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target.relative_to(application).as_posix())
        if source.name.lower() == 'licenses_strawberry_perl.zip':
            extract_notice_zip(source, target.parent / 'Strawberry-Perl-notices')
    # Preserve notices shipped as wheel metadata, where upstream supplies them.
    for name in ('PySide6-Essentials', 'shiboken6', 'tzdata', 'PyInstaller'):
        try:
            package = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        for item in package.files or []:
            if not _is_notice(item.name):
                continue
            source = Path(package.locate_file(item))
            if not source.is_file():
                continue
            target = destination / 'python-packages' / name / Path(str(item)).name
            target.parent.mkdir(parents=True, exist_ok=True)
            # Same-named notices from distinct paths must not overwrite each other.
            if target.exists() and target.read_bytes() != source.read_bytes():
                target = target.with_name(sha256(source)[:12] + '-' + target.name)
            shutil.copy2(source, target)
            copied.append(target.relative_to(application).as_posix())
    return sorted(set(copied))


def _component(relative):
    name = relative.lower()
    if name.startswith('licenses/'):
        return 'notice-materials'
    if 'tools/ffprobe/' in name or 'tools/ffmpeg/' in name:
        return 'ffprobe-and-static-dependencies'
    if 'tools/exiftool/' in name or any(part in name for part in ('perl532', 'libgcc_', 'libstdc++', 'libwinpthread')):
        return 'exiftool-perl-and-native-dependencies'
    if 'pyside6/' in name or 'shiboken6/' in name:
        return 'qt-pyside-shiboken-and-native-dependencies'
    if 'libssl' in name or 'libcrypto' in name:
        return 'openssl-runtime'
    if name.startswith('_internal/'):
        return 'python-or-other-runtime'
    return 'application-and-documentation'


def _pe_version(path):
    if path.suffix.lower() not in ('.dll', '.exe', '.pyd'):
        return None
    try:
        import pefile
    except ImportError:
        return None
    pe = pefile.PE(str(path), fast_load=True)
    try:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
        values = {}
        for group in getattr(pe, 'FileInfo', []):
            for entry in group:
                for table in getattr(entry, 'StringTable', []):
                    for key, value in table.entries.items():
                        if key.decode(errors='replace') in ('CompanyName', 'FileVersion', 'ProductName', 'ProductVersion', 'OriginalFilename', 'LegalCopyright'):
                            values[key.decode(errors='replace')] = value.decode(errors='replace')
        return values or None
    finally:
        pe.close()


def audit_distribution(application, source_commit):
    application = Path(application)
    notices = collect_notices(application)
    files = []
    for path in sorted(application.rglob('*')):
        if not path.is_file() or path.name in ('distribution-inventory.json', 'distribution-review.json', 'SHA256SUMS.txt', 'build-manifest.json', 'self-test.json'):
            continue
        relative = path.relative_to(application).as_posix()
        entry = {'path': relative, 'sha256': sha256(path), 'size': path.stat().st_size,
                 'component_hint': _component(relative)}
        version = _pe_version(path)
        if version:
            entry['pe_version'] = version
        files.append(entry)
    inventory = {'schema_version': 1, 'commit': source_commit, 'files': files,
                 'preserved_upstream_notices': notices,
                 'classification_note': 'Component hints are triage aids, not license determinations.'}
    (application / 'distribution-inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    components = sorted({file['component_hint'] for file in files} - {'notice-materials', 'application-and-documentation'})
    review = {'schema_version': 1, 'commit': source_commit, 'public_distribution_approved': False,
              'components': [{'id': component, 'status': 'needs-review'} for component in components],
              'remaining_checks': ['Match actual binary versions/configurations to corresponding source and upstream copyright notices.',
                                   'Include all required source/build materials and record their checksums.',
                                   'Verify Qt library replacement instructions on Windows.']}
    (application / 'distribution-review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
    return inventory
