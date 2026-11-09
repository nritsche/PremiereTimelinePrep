# Third-party components

The project license applies only to original project code. Bundled components
retain their own copyright and license terms. This inventory is a starting point,
not a declaration that an unreviewed binary is ready for public distribution.

| Component | Upstream terms and source | Build use |
| --- | --- | --- |
| Python | [PSF license and notices](https://docs.python.org/3/license.html), [source](https://www.python.org/downloads/source/) | Interpreter and standard library bundled by PyInstaller |
| Qt / PySide6 / Shiboken | [Qt for Python licensing](https://doc.qt.io/qtforpython-6/), [Qt licensing](https://doc.qt.io/qt-6/licensing.html), [source](https://code.qt.io/cgit/pyside/pyside-setup.git/) | Core, Gui, Widgets and runtime dependencies; release installer uses Essentials rather than the all-modules metapackage |
| FFprobe / FFmpeg | [FFmpeg legal information](https://www.ffmpeg.org/legal.html), [source](https://git.ffmpeg.org/ffmpeg.git) | Separate bundled command-line executable; inspect the exact build configuration and linked libraries |
| Gyan FFmpeg Windows build | [Build information and source links](https://www.gyan.dev/ffmpeg/builds/) | Upstream describes its Windows builds as GPLv3; this must not be mislabeled LGPL-only |
| ExifTool and Windows runtime | [License and source](https://exiftool.org/) | Same terms as Perl; include the accompanying Windows runtime and its notices |
| tzdata | [IANA timezone database](https://www.iana.org/time-zones), [Python package source](https://github.com/python/tzdata) | Timezone rules for systems without a timezone database |
| PyInstaller | [License and distribution exception](https://pyinstaller.org/en/stable/license.html), [source](https://github.com/pyinstaller/pyinstaller) | Build tooling and executable bootloader |

`build-manifest.json` records installed package versions, tool version strings,
staged tool-file hashes, the source commit and executable hash. Build inputs are
pinned in `requirements-build.txt` and the Windows workflow. Only required tool
executables, neighboring DLLs, ExifTool runtime files, and adjacent notices are
staged; unrelated FFmpeg executables are excluded.

Before publishing binary downloads, inventory the actual PyInstaller output,
including Qt plugins and transitive libraries. Put the applicable full license
and copyright notices in `licenses/`, preserve upstream notices, and prepare the
corresponding source/build materials required by the chosen distribution terms.
A URL to a moving upstream branch is not a substitute for corresponding source.
Check replacement/relinking requirements for the packaged Qt libraries.

New portable builds also include `distribution-inventory.json` with actual file
hashes and PE version metadata, `distribution-review.json` with explicitly open
review items, preserved/unpacked upstream notice collections, and upstream build
configuration output. See [review evidence](docs/THIRD_PARTY_REVIEW.md) and
[library replacement instructions](docs/LIBRARY_REPLACEMENT.md).

The maintainer must complete `docs/RELEASE_CHECKLIST.md` before publishing a
release. Packaging and automated tests do not establish license compliance.
