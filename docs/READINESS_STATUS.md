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

Still required from the maintainer / target environment:

1. Run the updated Windows workflow and test on a clean Windows machine.
2. Complete exact bundled-dependency copyright/license/source/relinking review.
   Standard license texts and provenance tooling are included, but do not by
   themselves complete this review. Supply corresponding third-party source/build materials.
3. Test the XML inside Premiere and record real results in PREMIERE_VALIDATION.md.
4. Enable repository secret scanning/private vulnerability reporting where available,
   review Git history and publish only after the appropriate release checklist passes.

No repository visibility change, tag, or public release is performed by these changes.
