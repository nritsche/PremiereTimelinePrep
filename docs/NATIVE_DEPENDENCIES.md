# Native dependency evidence and remaining checks

Baseline: private Windows review build
[42621680460](https://github.com/nritsche/PremiereTimelinePrep/actions/runs/42621680460),
source commit `e4c7c06`. The corresponding file hashes and version evidence are
recorded in `third_party/native-review-baseline.json`. This is evidence, not public
distribution approval.

| Component | Observed version/evidence | Upstream match / remaining check |
| --- | --- | --- |
| OpenSSL | 3.0.16 and 3.5.9, from actual DLL version resources | Exact upstream Git commits resolved for both; collect their actual terms and attribution files, not the historical 1.1.1i notice |
| XZ/liblzma | 5.2.4 beside Perl; 5.4.6 at the runtime root | Both upstream version commits resolved; preserve each version's applicable notices |
| Perl | 5.32.1; build identifies Strawberry Perl 5.32.1.1 | Upstream Perl source resolved; provider configuration retained; any provider patches still need matching |
| GCC runtime | Staged runtime built with GCC 8.3.0; compiler reported by Perl -V | Upstream GCC 8.3.0 resolved; retain runtime exception and applicable notices/patch evidence |
| MinGW winpthreads | MinGW-w64 6.0.0 from the provider notice; duplicate bytes match | Upstream version commit resolved; applicable runtime terms and provider patches need review |
| Mesa software renderer | Mesa 11.2.2, LLVM 3.6.2 strings in the exact hashed DLL | Official archived sources and Qt build instructions identified; preserve upstream terms/attributions |
| Microsoft runtime | MSVC 14.42.34438.0 and 14.44.35211.0; UCRT 10.0.26100.1742 | Check the appropriate redistribution terms and allowed files; this is not a requirement to obtain Microsoft's source code |
| Runtime-root libgcc_s_seh-1.dll | Different bytes from the GCC library in ExifTool; no usable PE version | Remains unidentified. New builds record its actual input origin and, where available, installed-package file-hash evidence instead of guessing its version |

The ExifTool notice archive says OpenSSL 1.1.1i. It is historical provider evidence;
it does not identify the two OpenSSL 3 DLL versions actually shipped. The native
source collector retrieves the observed versions separately and preserves their
source-shipped notices. The original archive remains intact rather than being
rewritten to claim it describes a newer binary.

## Collected evidence

Private review build [42689103605](https://github.com/nritsche/PremiereTimelinePrep/actions/runs/42689103605)
passed all Linux/Windows tests and its packaged-app self-test. It collected all nine
native source archives successfully. Their observed archive hashes are now pinned
in native-source-lock.json. The native notice extraction includes the actual
OpenSSL 3 version materials rather than relying solely on the historical notice.
The trace narrowed the unmatched root GCC DLL to a host MinGW installation;
further provider identification is kept distinct from DLL compiler-version proof.

## What the private review build produces

- `native-dependency-review.json`: per-file source/version evidence, notice
  mismatches, and unresolved files. It never grants public distribution approval.
- `binary-origins.json`: matched binary input origins with absolute build-machine
  paths omitted. MSYS2 package identification requires an exact installed-file hash.
- Native source archives and checksums in the private source-review artifact,
  with explicit errors if a download fails. Source URLs for GitHub projects use
  exact commit IDs, not moving branches.
- Actual source-shipped licenses/notices copied beside the portable application.
- The FFmpeg provider README's 37 reported external-library versions, retained
  as an explicit list whose source/build matching is still open.

Source provision depends on each component's terms. Permissive components may
require notices rather than corresponding source; proprietary redistributables
have their own conditions; copyleft components can impose source/build obligations.
Collecting source archives is useful evidence but does not mean every DLL must
be rebuilt or every notice-only component has a source-delivery obligation.

## Remaining release work

1. Review the generated notice materials for the actual versions. Resolve the
   different runtime-root GCC library using the new origin report.
2. Match the FFmpeg static dependencies to exact source/build materials required
   by their terms. The provider README gives versions, not a complete source bundle.
3. Confirm the remaining provider patch/build evidence and Qt replacement path;
   record an explicit per-component decision/rationale in the release review.
4. Assemble and checksum the required distribution materials, then run the guarded
   draft-release workflow. Public binary uploads stay disabled until approval.

No runtime libraries were removed as part of this review. Size measurements in the
baseline are: launcher 1.97 MiB, FFprobe 100.35 MiB, software renderer 19.68 MiB.
A substantially smaller FFprobe or removing the renderer needs compatibility
validation; neither is described as a zero-downside optimization.
