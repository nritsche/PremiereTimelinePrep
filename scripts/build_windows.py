"""Stage only required runtime files and record Windows build provenance."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def copy_tool_folder(executable: Path, destination: Path, expected_name: str) -> None:
    if not executable.is_file():
        raise ValueError("Missing required executable: {}".format(executable))
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, destination / expected_name)
    # Explicit runtime dependencies; do not bundle ffmpeg/ffplay or installers.
    for item in executable.parent.iterdir():
        if item.is_dir() and item.name.lower() == 'exiftool_files':
            shutil.copytree(item, destination / item.name, dirs_exist_ok=True)
        elif item.is_file() and (item.suffix.lower() == '.dll' or
                                any(word in item.name.lower() for word in ('license', 'copying', 'notice', 'readme'))):
            shutil.copy2(item, destination / item.name)
    for item in executable.parent.parent.iterdir():
        if item.is_file() and any(word in item.name.lower() for word in ('license', 'copying', 'notice', 'readme')):
            shutil.copy2(item, destination / item.name)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    from distribution_audit import audit_distribution
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffprobe', required=True, type=Path)
    parser.add_argument('--exiftool', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Build on Windows; PyInstaller does not cross-compile')
    tools_root = ROOT / 'build-tools' / 'tools'
    if tools_root.exists():
        shutil.rmtree(tools_root)
    for name, executable in [('ffprobe', args.ffprobe), ('exiftool', args.exiftool)]:
        copy_tool_folder(executable.resolve(), tools_root / name, name + '.exe')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--windowed', '--name', 'PremiereTimelinePrep', '--collect-data', 'tzdata',
               '--hidden-import', 'tzdata', '--add-data', '{}{}tools'.format(tools_root, os.pathsep),
               str(ROOT / 'app' / 'main.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    dist = ROOT / 'dist' / 'PremiereTimelinePrep'
    staged = {}
    for path in tools_root.rglob('*'):
        if path.is_file():
            staged[path.relative_to(tools_root).as_posix()] = sha256(path)
    versions = {}
    for tool, flag in [('ffprobe', '-version'), ('exiftool', '-ver')]:
        executable = tools_root / tool / (tool + '.exe')
        versions[tool] = subprocess.check_output([str(executable), flag], text=True,
            encoding='utf-8', errors='replace', timeout=30).splitlines()[0]
    build_info = dist / 'upstream-build-info'
    build_info.mkdir(exist_ok=True)
    ffprobe = tools_root / 'ffprobe' / 'ffprobe.exe'
    for flag, filename in [('-buildconf', 'ffprobe-build-configuration.txt'), ('-L', 'ffprobe-license.txt')]:
        output = subprocess.check_output([str(ffprobe), flag], stderr=subprocess.STDOUT, text=True,
                                         encoding='utf-8', errors='replace', timeout=30)
        (build_info / filename).write_text(output, encoding='utf-8')
    perl = tools_root / 'exiftool' / 'exiftool_files' / 'perl.exe'
    if perl.is_file():
        output = subprocess.check_output([str(perl), '-V'], stderr=subprocess.STDOUT, text=True,
                                         encoding='utf-8', errors='replace', timeout=30)
        (build_info / 'perl-build-configuration.txt').write_text(output, encoding='utf-8')
    from PySide6.QtCore import qVersion
    manifest = {
        'qt_version': qVersion(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'python': sys.version,
        'packages': dict(sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions() if d.metadata['Name'])),
        'tools': versions,
        'bundled_tool_sha256': staged,
        'executable_sha256': sha256(dist / 'PremiereTimelinePrep.exe'),
        'distribution_status': 'experimental build; third-party source/license review required before public release',
    }
    (dist / 'build-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for name in ('README.md', 'THIRD_PARTY_NOTICES.md', 'LICENSE'):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, dist / name)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        (dist / 'licenses').mkdir(exist_ok=True)
        shutil.copy2(python_license, dist / 'licenses' / 'Python-LICENSE.txt')
    shutil.copytree(ROOT / 'docs', dist / 'docs', dirs_exist_ok=True)
    if (ROOT / 'licenses').is_dir():
        shutil.copytree(ROOT / 'licenses', dist / 'licenses', dirs_exist_ok=True)
    from binary_origins import record_binary_origins
    record_binary_origins(ROOT / 'build/PremiereTimelinePrep/Analysis-00.toc', dist, tools_root, ROOT)
    audit_distribution(dist, manifest['commit'])
    from native_dependency_review import review_native_dependencies
    review_native_dependencies(dist)
    audit_distribution(dist, manifest['commit'])
    manifest['distribution_inventory_sha256'] = sha256(dist / 'distribution-inventory.json')
    manifest['package_layout'] = 'portable-folder-with-replaceable-shared-libraries'
    (dist / 'build-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (dist / 'SHA256SUMS.txt').write_text('{}  PremiereTimelinePrep.exe\n'.format(manifest['executable_sha256']), encoding='utf-8')
    print('Windows build created in {}'.format(dist))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
