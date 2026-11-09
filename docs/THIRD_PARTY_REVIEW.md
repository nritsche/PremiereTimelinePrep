# Binary distribution review evidence

Status: **in progress; public executable distribution is not approved**.
This document records observations and remaining evidence, not legal clearance.

## What the inspected build contains

The Windows artifact from commit `14b616b` contained Python 3.12.10,
PySide6-Essentials/Shiboken 6.12.0, Gyan FFprobe 9.0.2, ExifTool 13.59,
and tzdata 2025.2. Inspecting its PyInstaller archive found 1,336 members:
Qt Core/Gui/Widgets/Network/Svg and image/TLS/platform plugins; Python extensions;
Microsoft runtime DLLs; OpenSSL; and Perl/GNU native runtimes.
The inventory is broader than the packages listed in requirements.txt.

The ExifTool runtime carries its own LICENSE plus `Licenses_Strawberry_Perl.zip`
with 198 entries including copyrights, licenses, version/source information and
some patches. The new portable packaging preserves both the original archive and
an unpacked notice collection. A generic GPL text alone did not establish review
completion for these dependencies.

## Evidence generated for new builds

- `distribution-inventory.json`: actual application files, SHA-256, sizes, and
  Windows PE version/company/copyright fields where available.
- `distribution-review.json`: component groups and explicit **needs-review**
  status. Builds never generate a public-distribution approval.
- `licenses/upstream/`: notices actually shipped in the runtime or installed
  package metadata. ExifTool's upstream notice collection is unpacked safely.
- `upstream-build-info/`: FFprobe configuration/license output and Perl build
  configuration, in addition to versions in `build-manifest.json`.
- `docs/LIBRARY_REPLACEMENT.md`: portable shared-library layout and rebuild path.

Manual private workflows can select **collect_primary_sources**. That retrieves
primary source candidates for the pinned Python, Qt modules/PySide bindings,
FFmpeg and ExifTool, records hashes, and preserves source-shipped license and
attribution files beside the application. The separate private source artifact
contains a download index and checksums, including explicit failures.

Verified source references include the archived Qt 6.12.0 source releases,
Python 3.12.10, FFmpeg commit `946fcce07b6dcd0331c8cc609192aeff5e1924f8`
(linked by the Gyan 9.0.2 release page), and ExifTool 13.59 commit
`2200871d9cef988051d2a99d67df3bda6cbb30a8`. The direct current ExifTool source
URL returned 404 during review; the immutable upstream Git reference is used instead.
Private review run `42621680460` successfully collected all seven primary
archives; their observed SHA-256 values are pinned in the collector. The portable
Windows build and its executable self-test passed. The Gyan 9.0.2 ZIP's README was
also inspected directly; it lists external-library revisions. Builds preserve
that upstream README alongside the tool rather than discarding it.

These references are starting evidence, not proof that every binary was built
from unmodified sources with a known complete configuration.

## Native version matching progress

See [NATIVE_DEPENDENCIES.md](NATIVE_DEPENDENCIES.md) and the observed baseline in
`third_party/native-review-baseline.json`. Both observed OpenSSL versions, both
XZ versions, Perl, GCC and MinGW now have exact version references; the renderer
was identified as Mesa 11.2.2/LLVM 3.6.2 by its byte-matched DLL. The old Perl
OpenSSL notice does not match the current OpenSSL DLLs and is not used as their
license attribution. One different runtime-root GCC DLL needs input-origin tracing.

The private source collector now gathers nine matched native source candidates (two OpenSSL, two XZ, Perl, GCC, MinGW-w64, Mesa and LLVM)
and their notices separately. Version matching is not an automatic approval of
provider build correspondence or legal terms. Microsoft redistributables require
their redistribution terms, not an invented corresponding-source requirement.

## What must still be resolved

1. Match all inventoried DLLs and Qt plugins to their actual upstream terms and
   corresponding versions. Hints in the inventory are not license determinations.
2. Match the Gyan static build's enabled external libraries to exact source/build
   materials. The FFmpeg source archive alone does not include all those libraries.
3. Match ExifTool's Perl/native runtime and compiler libraries to exact source,
   patches, build instructions and any applicable runtime exceptions.
4. Complete Qt third-party/native dependency and Windows runtime notice review;
   verify library replacement/rebuild on Windows.
5. Assemble a corresponding-source ZIP with an explicit completed
   `distribution-review.json`, exact inventory hash, per-component rationale,
   and hashes/paths for the included notice and source materials. Document any
   component for which corresponding source is not required under the chosen terms.

The draft-release helper rejects an incomplete/mismatched review, missing groups,
or altered files. It checks evidence consistency; a maintainer still must review
whether those materials satisfy the applicable license terms. It does not certify
legal sufficiency. Keep public binary uploads disabled until that review passes.
