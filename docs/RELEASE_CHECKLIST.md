# Public release checklist

Source publication and executable publication have different prerequisites.
Check boxes only when the work has actually been verified. Automated tests do not
complete the legal review or the Premiere integration check.

## Source publication

- [ ] Maintainer selected the project license; LICENSE and pyproject metadata agree.
- [ ] Review all Git history for credentials and personal data; enable GitHub secret scanning where available.
- [ ] Confirm personal reports, exported XML, sample footage and screenshots with real paths are absent from Git history.
- [ ] Run tests on Linux and Windows, including Python 3.11, the supported minimum.
- [ ] Review README, supported-media limitations, privacy notes, and issue templates.

## Executable distribution

- [ ] Latest Windows workflow passes tests and the actual packaged-app self-test.
- [ ] Launch on a clean Windows machine without Python or metadata tools on PATH.
- [ ] Test cancelling and closing a scan; reopen a saved review; verify Unicode filenames.
- [ ] Review the exact build manifest and PyInstaller runtime inventory, including DLLs/plugins.
- [ ] Include applicable full copyright/license notices for Python, Qt/PySide/Shiboken and transitive libraries, FFprobe and linked libraries, ExifTool/Perl runtime, tzdata, and any other bundled component.
- [ ] Include exact corresponding source and build/configuration materials required by each component's distribution terms. Verify source correspondence to the bundled hashes/versions.
- [ ] Verify Qt library replacement/relinking requirements and document the supported rebuild/replacement method.
- [ ] Put reviewed full license texts under licenses/; rebuild so they accompany the artifact.
- [ ] Before enabling public binary artifact downloads, set the repository variable `PUBLIC_BINARY_DISTRIBUTION_REVIEWED=true` only after the distribution review passes. Public repositories otherwise build/test without uploading executables; private development artifacts remain available.
- [ ] Prepare a corresponding-source ZIP and record its SHA-256. Do not substitute only moving upstream links.
- [ ] Run the manual draft-release workflow with the successful build run ID and reviewed source ZIP. It rejects missing project/upstream license materials and failed artifact self-tests.
- [ ] Review the draft assets and notes. Publish manually only after the checks above are complete.

Artifacts and GitHub Releases include checksums for integrity. Builds are not
code-signed; document Windows SmartScreen warnings without telling users to disable
security software. Signing can be added when a suitable certificate is available.
The build is pinned and records provenance; bit-for-bit reproducibility is not claimed.

## Premiere compatibility

- [ ] Follow README's import checklist and record results in PREMIERE_VALIDATION.md.
- [ ] Check long clips, constant and variable rates, mixed rates, linked audio, Unicode paths, excluded/undated clips, relinking, and save/reopen.
- [ ] Do not describe the exporter as verified or production-ready until these results exist.
