# Premiere Timeline Prep

Premiere Timeline Prep prepares footage metadata and recording-time order for an Adobe Premiere Pro edit. The current GUI supports folder selection, background scanning, readable timestamp review, individual timestamp overrides, manual camera grouping, and camera-group time corrections. Session reports can be exported as JSON or CSV. Experimental Premiere XML timeline export is available for import testing.

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

Use **Export XML…** after scanning with FFprobe installed. Included clips are placed back-to-back in capture-time order, with unknown capture times last. Search filters do not change inclusion. The first included clip sets the sequence frame rate and dimensions; source rates are retained and positions use sequence frames. Embedded audio channels are exported on linked audio tracks. No media is copied or transcoded.

Export uses Final Cut Pro 7 `xmeml` version 5, based on [Apple’s encoding documentation](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/FinalCutPro_XML/Basics/Basics.html). This is distinct from Final Cut Pro X `.fcpxml`, which [Premiere cannot directly import](https://helpx.adobe.com/ca/premiere/desktop/organize-media/import-files/migrate-from-final-cut-pro-x.html).

This exporter is experimental. Automated checks verify XML structure and timing but do not prove Premiere compatibility. Audio channel details require a fresh scan if the session predates XML export. Missing durations, dimensions, unsupported rates, and missing audio channel details block export rather than silently omit media. Variable-frame-rate footage uses its reported average rate and requires particular attention during import review. Paths are absolute file URLs: moving files or importing on another computer requires relinking.

### Manual Premiere integration check

1. Scan a small sample with at least two clips, including audio; export XML. Include mixed frame rates and a filename with spaces or accented characters when available.
2. In Premiere, create a test project and use File > Import to select the XML. Record the Premiere version and any import warnings.
3. Confirm the Project panel contains the expected media and sequence. Open the sequence and check clip order, excluded clips, sequence settings, and media links.
4. Play the first and last seconds of each clip. Check picture, all audio channels, linked video/audio selection, clip boundaries, and sync, especially for mixed or variable frame rates.
5. Compare timeline duration with the included footage duration, allowing frame rounding. Save, reopen, and verify again. Keep this checklist incomplete until tested in Premiere.
