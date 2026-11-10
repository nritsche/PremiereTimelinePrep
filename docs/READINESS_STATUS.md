# Readiness work from the repository audit

Implemented by the release-readiness changes:

- Group-aware timestamp ranking, malformed-date retention, FFprobe stream-tag dates.
- Camera timezone selection; Linux change times no longer mislabeled creation times.
- Strict session number/type validation, non-finite-number rejection, loading limits.
- Media/alias overwrite protection and spreadsheet-formula neutralization in CSV.
- Cancellable metadata process groups, cancellable discovery, safe asynchronous close.
- Failed/cancelled scans retain the current review; unavailable folders are reported.
- Unsaved-session prompts and date editing for undated clips.
- Full stream metadata retained; unsupported stream/layout/rotation/timing cases block XML export.
- Pinned release inputs, restricted runtime staging, build manifest and executable hashes.
- Linux/Python-minimum CI and a Windows packaged-executable self-test using synthetic media.
- A draft-release process that verifies trusted artifacts and source-bundle hashes.
- Sanitized documentation screenshot, walkthrough, privacy/security guidance, issue template.
- Regression tests for the audit findings and runtime staging.
- Standard MIT project license, full license text, and SPDX package metadata.
- Portable shared-library packaging, full file/PE inventory and original upstream notice preservation.
- Optional private primary-source collection and review evidence tied to the exact inventory hash.
- Native version/source matching, historical-notice mismatch detection, and build-input origin tracing.
- A synthetic media comparison gate for packaged FFprobe across eight video formats with audio.
- Visual timeline review with large thumbnails, still-frame scrubbing, automatic
  camera/folder source labels and shared XML/preview frame boundaries. Windows
  packaging includes FFmpeg and requires a real thumbnail decode in its self-test.

Still required from the maintainer / target environment:

1. Test on a clean Windows machine. Private build 42691353224 passed Linux 3.11–3.13, 84 Windows tests, and its packaged self-test. The newer probe-comparison gate requires its own CI result.
2. Complete exact bundled-dependency copyright/license/source/relinking review.
   Standard license texts and provenance tooling are included, but do not by
   themselves complete this review. Supply corresponding third-party source/build materials.
3. Test the XML inside Premiere and record real results in PREMIERE_VALIDATION.md.
4. Enable repository secret scanning/private vulnerability reporting where available,
   review Git history and publish only after the appropriate release checklist passes.

No repository visibility change, tag, or public release is performed by these changes.
