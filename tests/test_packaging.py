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
