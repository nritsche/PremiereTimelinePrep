# Premiere Timeline Prep

Premiere Timeline Prep prepares footage metadata and recording-time order for an Adobe Premiere Pro edit. The current GUI supports folder selection, background scanning, readable timestamp review, individual timestamp overrides, manual camera grouping, and camera-group time corrections. Session reports can be exported as JSON or CSV. Premiere interchange generation is a subsequent stage.

## Current capabilities

- Recursively discovers the supported video extensions and avoids duplicates across overlapping folders and hard links.
- Reads technical stream information with FFprobe and broad metadata with ExifTool when installed.
- Keeps raw timestamp metadata, filesystem times, filename dates, and parsed UTC instants as reviewable candidates.
- Prefers explicit recording dates, then creation dates, then filename dates, and finally weak filesystem times. Filesystem creation/modification dates are weak because copying changes them. Naive camera timestamps are interpreted as UTC by default; this is configurable for callers. An explicit offset is honored and normalized to UTC.
- Flags sentinel dates, out-of-range dates, and conflicting embedded date fields without discarding them.
- Provides camera-group time offsets, reference-clip correction, and per-clip override primitives.
- Includes a PySide6 folder selection and asynchronous scan window with searchable, sortable metadata review.
- Shows full candidate and warning details for the selected clip. Missing FFprobe/ExifTool are presented as setup notices, rather than repeated clip timestamp warnings.
- Allows individual time overrides, manual source assignment, and camera-group offsets or reference-time corrections during the current scan session.
- Exports JSON audit reports with raw metadata, original timestamp candidates, corrected selections, and inclusion flags; CSV inventories list clips chronologically with unknown times last. Reports include all scanned clips regardless of search filters.
- Preserves clip inclusion choices when timestamps or camera groups change. Open a JSON report with “Open session…” to restore footage review, camera groups, corrections, and inclusion choices without rescanning. Unavailable media paths are reported after opening; CSV files are review inventories and cannot be reopened as sessions.

The selection policy is deliberately visible in `app/core/timestamp_resolver.py`. Camera vendors use inconsistent QuickTime conventions, and a timestamp alone cannot establish a camera's timezone. Review warnings and raw candidates before applying corrections.

## Setup

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e '.[gui,dev]'
```

FFprobe and ExifTool are optional during development and are detected from `PATH`. The scanner continues if either tool is missing or fails on an individual file. The Windows build will bundle or explicitly locate these tools; they are not installed by this package. Media processing is offline.

Run unit tests with `pytest`.

## Windows build

`.github/workflows/build-windows.yml` builds on `windows-latest` because PyInstaller does not cross-compile Windows executables from Ubuntu. The workflow installs FFmpeg and ExifTool on its Windows runner, stages FFprobe, ExifTool, and neighboring runtime files, runs the tests, then uploads `PremiereTimelinePrep.exe` as a workflow artifact. Run it with `workflow_dispatch`, push to `main`/`master`, or push a `v*` tag. The packaged application locates those bundled tools without requiring them on the end user's `PATH`.

The same staging/build step can be run locally on Windows with Python 3.11+ after installing `.[gui,dev]` and providing the paths to `scripts/build_windows.py`:

```powershell
python scripts/build_windows.py --ffprobe C:\path\to\ffprobe.exe --exiftool C:\path\to\exiftool(-k).exe
```

## Premiere interchange status

No Premiere compatibility claim is made yet. The XML generator is intentionally not implemented until its xmeml structure can be checked against reliable Premiere import requirements. XML unit tests alone cannot prove Premiere compatibility. Before release, follow the manual Premiere integration procedure to open an exported project and inspect both the Project panel and timeline. The initial path policy will use absolute media paths; moving media after generation will require relinking.
