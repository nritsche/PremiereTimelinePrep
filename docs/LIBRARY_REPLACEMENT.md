# Replacing libraries in the portable Windows package

The portable package is an entire folder, not a self-contained single file.
Keep `PremiereTimelinePrep.exe`, `_internal/`, `licenses/` and the documentation
together. The app loads shared libraries from `_internal/`; it does not verify
against a vendor signature or forbid modified libraries. The recorded hashes
are integrity/provenance information, not a restriction on modification.

Qt/PySide6 is used under its applicable open-source terms. Users may modify the
covered libraries and debug those modifications, including reverse engineering
as allowed by their licenses. Our MIT project license does not remove these rights.

## Compatible library replacement

1. Work on a copy of the portable package and retain the original for comparison.
2. Read `build-manifest.json` and `distribution-inventory.json` for the actual
   Python, Qt, PySide6, Shiboken and native runtime versions and file locations.
3. Build compatible Windows x64 Qt/PySide6/Shiboken libraries from the supplied
   corresponding sources and their upstream build instructions. Match the Python
   ABI, Qt major/minor ABI, compiler/runtime and required plugins. An arbitrary
   DLL from a different Qt release is not necessarily compatible.
4. Replace the matching library files under `_internal/PySide6/` and, for modified
   bindings, `_internal/shiboken6/` and associated `.pyd`/DLL files. Keep the matched
   plugins and supporting libraries consistent with the replacement build.
5. Run the app and the documented synthetic media test, then verify the normal
   scan/review/export behavior. Reverting the copied folder restores the original.

No completed Windows replacement test is claimed yet; record such a test in the
release review. Upstream source/build materials must accompany a public release
where required. The existing primary-source collector is not by itself that approval.

## Rebuild the application around modified libraries

The full original application source is MIT-licensed and is supplied as a release
source archive or can be cloned from the tagged source commit. Use the Python
version recorded in the build manifest, install the release build requirements,
then replace the stock Qt/PySide/Shiboken installation with the compatible modified
build. Follow README's Windows build commands using those installed libraries.
The build does not impose an original-library hash check and does not use code
signing to prevent running your rebuilt version.

FFprobe and ExifTool run as separate programs under `_internal/tools/`. Replace
them together with their required runtime files when using compatible modified
versions. Follow each component's own source/build instructions and license terms.
