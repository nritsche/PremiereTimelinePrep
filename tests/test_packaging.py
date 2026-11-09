from pathlib import Path
import importlib.util


def builder_module():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'build_windows.py'
    spec = importlib.util.spec_from_file_location('test_windows_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tool_staging_excludes_unrelated_executables_and_keeps_runtime(tmp_path):
    module = builder_module()
    source = tmp_path / 'distribution' / 'bin'
    source.mkdir(parents=True)
    for name in ['ffprobe.exe', 'ffmpeg.exe', 'ffplay.exe', 'runtime.dll', 'installer.zip']:
        (source / name).write_bytes(b'fixture')
    (source.parent / 'LICENSE.txt').write_text('upstream notice', encoding='utf-8')
    destination = tmp_path / 'staged'
    module.copy_tool_folder(source / 'ffprobe.exe', destination, 'ffprobe.exe')
    assert {p.name for p in destination.iterdir()} == {'ffprobe.exe', 'runtime.dll', 'LICENSE.txt'}
    runtime = source / 'exiftool_files'
    runtime.mkdir()
    (runtime / 'perl.dll').write_bytes(b'fixture')
    exiftool = source / 'exiftool(-k).exe'
    exiftool.write_bytes(b'fixture')
    module.copy_tool_folder(exiftool, tmp_path / 'exiftool', 'exiftool.exe')
    assert (tmp_path / 'exiftool/exiftool.exe').exists()
    assert (tmp_path / 'exiftool/exiftool_files/perl.dll').exists()


def audit_module():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'distribution_audit.py'
    spec = importlib.util.spec_from_file_location('test_distribution_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_perl_notices_preserved_and_inventory_is_not_approval(tmp_path, monkeypatch):
    import json
    import zipfile
    module = audit_module()
    monkeypatch.setattr(module, '_pe_version', lambda path: None)
    runtime = tmp_path / '_internal/tools/exiftool/exiftool_files'
    runtime.mkdir(parents=True)
    (runtime / 'LICENSE').write_text('exact upstream license', encoding='utf-8')
    with zipfile.ZipFile(runtime / 'Licenses_Strawberry_Perl.zip', 'w') as archive:
        archive.writestr('libssl/LICENSE', 'original copyright and license')
        archive.writestr('libssl/_INFO_', 'original version and source information')
    (tmp_path / 'PremiereTimelinePrep.exe').write_bytes(b'synthetic executable')
    inventory = module.audit_distribution(tmp_path, 'a' * 40)
    preserved = tmp_path / 'licenses/upstream/tools/exiftool/exiftool_files'
    assert (preserved / 'LICENSE').read_text(encoding='utf-8') == 'exact upstream license'
    assert (preserved / 'Strawberry-Perl-notices/libssl/_INFO_').exists()
    assert any(row['path'].endswith('PremiereTimelinePrep.exe') for row in inventory['files'])
    assert all(len(row['sha256']) == 64 for row in inventory['files'])
    review = json.loads((tmp_path / 'distribution-review.json').read_text(encoding='utf-8'))
    assert review['public_distribution_approved'] is False
    assert review['components']


def test_notice_archive_cannot_escape_destination(tmp_path):
    import zipfile
    import pytest
    module = audit_module()
    archive = tmp_path / 'notices.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('../outside.txt', 'bad')
    with pytest.raises(ValueError, match='Unsafe path'):
        module.extract_notice_zip(archive, tmp_path / 'notices')
    assert not (tmp_path / 'outside.txt').exists()


def source_module():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'collect_primary_sources.py'
    spec = importlib.util.spec_from_file_location('test_source_collector', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_notice_extraction_preserves_attributions_not_code(tmp_path):
    import io
    import tarfile
    module = source_module()
    path = tmp_path / 'source.tar.gz'
    with tarfile.open(path, 'w:gz') as output:
        for name, content in [('qt/LICENSES/LGPL-3.0.txt', b'upstream terms'),
                              ('qt/src/qt_attribution.json', b'{}'), ('qt/src/main.cpp', b'code')]:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            output.addfile(info, io.BytesIO(content))
    destination = tmp_path / 'notices'
    assert module.extract_source_notices(path, destination) == 2
    assert (destination / 'qt/LICENSES/LGPL-3.0.txt').read_bytes() == b'upstream terms'
    assert not (destination / 'qt/src/main.cpp').exists()


def test_unavailable_primary_sources_remain_explicitly_unapproved(tmp_path, monkeypatch):
    import json
    module = source_module()
    (tmp_path / 'app').mkdir()
    manifest = {'commit': 'a' * 40, 'python': '3.12.10 (fixture)', 'qt_version': '6.12.0',
                'packages': {'PySide6-Essentials': '6.12.0', 'shiboken6': '6.12.0'},
                'tools': {'ffprobe': 'ffprobe version 9.0.2-essentials', 'exiftool': '13.59'}}
    (tmp_path / 'app/build-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(module, 'SOURCES', [('unavailable.tar.gz', 'https://example.invalid/source')])
    def unavailable(*args, **kwargs):
        raise OSError('fixture unavailable')
    monkeypatch.setattr(module.urllib.request, 'urlopen', unavailable)
    report = module.collect(tmp_path / 'app', tmp_path / 'sources')
    assert report['public_distribution_approved'] is False
    assert report['sources'][0]['status'] == 'unavailable'
    assert not (tmp_path / 'sources/unavailable.tar.gz').exists()


def test_source_notice_archive_rejects_windows_drive_paths(tmp_path):
    import io
    import tarfile
    import pytest
    path = tmp_path / 'source.tar.gz'
    with tarfile.open(path, 'w:gz') as output:
        member = tarfile.TarInfo('C:\\outside\\LICENSE')
        member.size = 1
        output.addfile(member, io.BytesIO(b'x'))
    with pytest.raises(ValueError, match='Unsafe source archive path'):
        source_module().extract_source_notices(path, tmp_path / 'notices')
