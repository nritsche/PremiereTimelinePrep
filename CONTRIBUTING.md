# Contributing

Use Python 3.11+ and install `pip install -e '.[gui,dev]'`. Run
`QT_QPA_PLATFORM=offscreen python -m pytest -q` on Linux; on Windows set that
environment variable in PowerShell before running pytest. CI checks Linux and
Windows; Windows packaging additionally uses requirements-build.txt.

Keep media files unchanged. Preserve original timestamp provenance and explain
assumptions in the review UI. Add regressions for behavior changes, use native
temporary paths and explicit UTF-8 in tests, and use synthetic or licensed media.
Never commit personal reports, recordings, credentials, or screenshots of raw
private metadata. See the issue template and docs/RELEASE_CHECKLIST.md.

Public binary releases require a separate dependency license/source review and
manual Premiere import validation. Do not describe untested compatibility as verified.
