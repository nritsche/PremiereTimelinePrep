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

## Secret scanning

Gitleaks 8.30.1 runs on every branch push and pull request, weekly, and before
Windows packaging/uploads or draft release creation. It scans the complete
available Git history with the upstream default rules and redacts findings in
logs. No findings are suppressed by a baseline. The CLI does not require a
Gitleaks Action license or a repository secret.

Install Gitleaks from https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1
and enable this clone's hooks to check every staged commit and scan history
before each push:

```sh
git config core.hooksPath .githooks
```

Gitleaks must be on PATH, or configure its absolute executable path with
`git config gitleaks.path /absolute/path/to/gitleaks`. Each clone needs this setup.
The hooks fail if the scanner is missing. CI remains independent of local hooks.
To scan manually: `gitleaks git --redact=100 --log-opts="--all --full-history" .`.

Actions run after a push reaches GitHub; they cannot retract an exposed secret.
Use GitHub push protection where available and require the Gitleaks check in
branch rules to prevent merging failed scans. Hooks can be bypassed and scanners
can miss secrets. If a real credential is found, revoke/rotate it immediately;
deleting it from the latest commit alone does not remove it from history.
