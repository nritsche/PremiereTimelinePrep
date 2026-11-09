import importlib.util
import json
from pathlib import Path


def module(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location('test_' + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def setup_review(tmp_path):
    lock = {'sources': [{'id': 'openssl-3.5.9', 'commit': 'a' * 40},
                        {'id': 'gcc-8.3.0', 'commit': 'b' * 40}], 'fingerprints': []}
    lock_path = tmp_path / 'lock.json'
    lock_path.write_text(json.dumps(lock), encoding='utf-8')
    config = tmp_path / 'upstream-build-info'
    config.mkdir()
    (config / 'perl-build-configuration.txt').write_text("gccversion='8.3.0'", encoding='utf-8')
    return lock_path


def test_native_match_uses_observed_openssl_version_not_old_notice(tmp_path):
    lock = setup_review(tmp_path)
    path = tmp_path / 'licenses/upstream/openssl'
    path.mkdir(parents=True)
    (path / '_INFO_').write_text('Package: openssl-1.1.1i\n', encoding='utf-8')
    rows = [{'path': '_internal/libcrypto-3-x64.dll', 'sha256': 'c' * 64,
             'pe_version': {'ProductVersion': '3.5.9'}}]
    (tmp_path / 'distribution-inventory.json').write_text(json.dumps({'commit': 'd' * 40, 'files': rows}), encoding='utf-8')
    report = module('native_dependency_review').review_native_dependencies(tmp_path, lock)
    assert report['matches'][0]['source_id'] == 'openssl-3.5.9'
    assert report['notice_mismatches'][0]['reported_package'] == 'openssl-1.1.1i'
    assert report['public_distribution_approved'] is False


def test_different_compiler_runtime_bytes_are_not_assigned_the_perl_compiler(tmp_path):
    lock = setup_review(tmp_path)
    rows = [{'path': '_internal/libgcc_s_seh-1.dll', 'sha256': 'a' * 64},
            {'path': '_internal/tools/exiftool/exiftool_files/libgcc_s_seh-1.dll', 'sha256': 'b' * 64}]
    (tmp_path / 'distribution-inventory.json').write_text(json.dumps({'commit': 'c' * 40, 'files': rows}), encoding='utf-8')
    report = module('native_dependency_review').review_native_dependencies(tmp_path, lock)
    assert report['matches'][0]['status'] == 'source-reference-unresolved'
    assert report['matches'][1]['source_id'] == 'gcc-8.3.0'


def test_binary_origins_preserve_identity_without_host_path(tmp_path):
    app = tmp_path / 'app'
    (app / '_internal').mkdir(parents=True)
    tools = tmp_path / 'tools/exiftool'
    tools.mkdir(parents=True)
    source = tools / 'runtime.dll'
    source.write_bytes(b'exact runtime')
    (app / '_internal/runtime.dll').write_bytes(source.read_bytes())
    toc = tmp_path / 'Analysis-00.toc'
    toc.write_text(repr([('runtime.dll', str(source), 'BINARY')]), encoding='utf-8')
    report = module('binary_origins').record_binary_origins(toc, app, tmp_path / 'tools', tmp_path)
    row = report['files'][0]
    assert row['provider_hint'] == 'staged-tool/exiftool'
    assert str(tmp_path) not in json.dumps(report)


def test_installed_package_provenance_requires_exact_hash(tmp_path):
    import gzip
    import hashlib
    code = module('binary_origins')
    msys = tmp_path / 'msys'
    dll = msys / 'mingw64/bin/runtime.dll'
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b'actual binary')
    package = msys / 'var/lib/pacman/local/gcc-libs-8.3.0'
    package.mkdir(parents=True)
    (package / 'files').write_text('%FILES%\nmingw64/bin/runtime.dll\n', encoding='utf-8')
    (package / 'desc').write_text('%NAME%\ngcc-libs\n\n%VERSION%\n8.3.0-1\n', encoding='utf-8')
    digest = hashlib.sha256(dll.read_bytes()).hexdigest()
    (package / 'mtree').write_bytes(gzip.compress(('./mingw64/bin/runtime.dll sha256digest=' + digest).encode()))
    assert code._pacman_package(dll, digest)['version'] == '8.3.0-1'
    assert code._pacman_package(dll, '0' * 64) is None


def test_ffprobe_external_versions_are_reported_not_assumed_reviewed(tmp_path):
    tool = tmp_path / '_internal/tools/ffprobe'
    tool.mkdir(parents=True)
    (tool / 'README.txt').write_text("external libraries' versions:\n\nx264 v0.165.3223\nlibssh 0.12.2\n", encoding='utf-8')
    rows = module('native_dependency_review').ffprobe_external_versions(tmp_path)
    assert [row['name'] for row in rows] == ['x264', 'libssh']
    assert all(row['status'] == 'version-reported-source-build-match-open' for row in rows)


def test_native_download_failure_does_not_approve_distribution(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    code = module('collect_native_sources')
    application = tmp_path / 'app'
    application.mkdir()
    lock = tmp_path / 'lock.json'
    source = {'id': 'openssl-3.5.9', 'commit': 'a' * 40,
              'source_url': 'https://api.github.com/repos/openssl/openssl/tarball/' + 'a' * 40}
    lock.write_text(json.dumps({'sources': [source]}), encoding='utf-8')
    review = {'commit': 'b' * 40, 'matches': [{'source_id': source['id'], 'path': '_internal/libcrypto.dll',
                'status': 'version-reference-matched-build-review-open'}], 'notice_mismatches': []}
    monkeypatch.setitem(sys.modules, 'native_dependency_review', SimpleNamespace(
        DEFAULT_LOCK=lock, review_native_dependencies=lambda *args: review))
    monkeypatch.setitem(sys.modules, 'collect_primary_sources', SimpleNamespace(extract_source_notices=lambda *args: 0))
    def unavailable(*args, **kwargs):
        raise OSError('fixture unavailable')
    monkeypatch.setattr(code.urllib.request, 'urlopen', unavailable)
    result = code.collect_native_sources(application, tmp_path / 'sources', lock)
    assert result['public_distribution_approved'] is False
    assert result['sources'][0]['status'] == 'unavailable'
    assert not list((tmp_path / 'sources').glob('*.tar.gz'))


def test_provider_version_remains_a_hint_not_a_dll_identity(tmp_path, monkeypatch):
    code = module('binary_origins')
    (tmp_path / 'gcc.exe').write_bytes(b'fixture')
    monkeypatch.setattr(code.subprocess, 'check_output', lambda *a, **kw:
                        'gcc (provider build) 13.2.0\nCopyright\n')
    evidence = code._provider_version(tmp_path)
    assert evidence['version_lines'] == ['gcc (provider build) 13.2.0']
    assert 'not proof' in evidence['scope']
