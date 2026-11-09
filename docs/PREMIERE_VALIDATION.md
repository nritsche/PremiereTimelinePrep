# Premiere validation record

Status: **not yet verified in Premiere**. XML generation and duration tests are
not an import or audiovisual sync test. No Premiere access is available in CI.

For each manual run, record:

- App commit/version, Windows version, Premiere version.
- Synthetic or licensed sample characteristics (avoid uploading private media).
- Import warnings and whether media links correctly.
- Clip order, inclusion, sequence settings, boundaries, frame-rate rounding.
- Audio channels, linked selection, playback and sync at the start and end of long clips.
- Variable-rate approximation results and any visible drift or missing frames.
- Save/reopen and moved-media relinking results.
- Pass/fail, remaining limitations, and a sanitized reproduction for each failure.

No successful manual runs have been recorded in this repository yet.
