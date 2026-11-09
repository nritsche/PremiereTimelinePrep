"""Record binary input provenance without publishing absolute build-machine paths."""
import ast
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from functools import lru_cache


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _records(value):
    if isinstance(value, (tuple, list)):
        if len(value) == 3 and all(isinstance(item, str) for item in value) and value[2] in ('BINARY', 'EXTENSION'):
            yield value
        else:
            for item in value:
                yield from _records(item)


@lru_cache(maxsize=8)
def _package_index(database):
    result = {}
    for package in database.iterdir():
        files = package / 'files'
        if not files.is_file():
            continue
        for name in files.read_text(encoding='utf-8', errors='replace').splitlines():
            if name and not name.startswith('%') and not name.endswith('/'):
                result.setdefault(name.lower(), []).append(package)
    return result


def _pacman_package(source, digest):
    # Match an installed MSYS2 package only if its recorded file hash agrees.
    for parent in source.parents:
        database = parent / 'var/lib/pacman/local'
        if not database.is_dir():
            continue
        relative = source.relative_to(parent).as_posix().lower()
        for package in _package_index(database).get(relative, []):
            mtree = package / 'mtree'
            if not mtree.is_file():
                continue
            with gzip.open(mtree, 'rt', encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    if line.split(' ', 1)[0].removeprefix('./').lower() != relative:
                        continue
                    recorded = re.search(r'sha256digest=([0-9a-f]{64})', line)
                    if not recorded or recorded.group(1) != digest:
                        continue
                    description = (package / 'desc').read_text(encoding='utf-8')
                    fields = {}
                    for field in ('NAME', 'VERSION', 'BASE', 'URL', 'BUILDDATE'):
                        match = re.search(r'%' + field + r'%\n([^\n]+)', description)
                        if match:
                            fields[field.lower()] = match.group(1)
                    return dict(fields, evidence='installed package mtree SHA-256 matches the exact binary')
    return None


def record_binary_origins(toc_path, application, tools_root, project_root, python_prefix=None):
    application, tools_root = Path(application), Path(tools_root).resolve()
    project_root = Path(project_root).resolve()
    python_prefix = Path(python_prefix or sys.base_prefix).resolve()
    analysis = ast.literal_eval(Path(toc_path).read_text(encoding='utf-8'))
    rows = {}
    for destination, source_name, kind in _records(analysis):
        source = Path(source_name).resolve()
        relative = destination.replace('\\', '/')
        if relative.startswith('/') or '..' in Path(relative).parts or ':' in relative:
            continue
        target = application / '_internal' / relative
        if not source.is_file() or not target.is_file():
            continue
        digest = _hash(source)
        if _hash(target) != digest:
            continue
        hint = 'unidentified-host-runtime'
        if source.is_relative_to(tools_root):
            hint = 'staged-tool/' + source.relative_to(tools_root).parts[0]
        elif 'site-packages' in source.parts:
            offset = source.parts.index('site-packages')
            hint = 'python-package/' + source.parts[offset + 1]
        elif source.is_relative_to(python_prefix):
            hint = 'python-installation'
        elif source.is_relative_to(project_root):
            hint = 'project-build-input'
        elif 'strawberry' in source.as_posix().lower():
            hint = 'host-strawberry-perl-installation'
        elif any(marker in source.as_posix().lower() for marker in ('msys64', 'mingw64', 'ucrt64')):
            hint = 'host-msys2-or-mingw-installation'
        row = {'path': '_internal/' + relative, 'sha256': digest, 'provider_hint': hint,
               'source_filename': source.name, 'kind': kind}
        package = _pacman_package(source, digest)
        if package:
            row['installed_package'] = package
        rows[row['path']] = row
    result = {'schema_version': 1, 'files': sorted(rows.values(), key=lambda row: row['path']),
              'scope': 'Build input origins; absolute host paths omitted. Provider hints do not establish license compliance.'}
    (application / 'binary-origins.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
