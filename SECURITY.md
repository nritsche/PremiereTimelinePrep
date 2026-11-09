# Security and privacy

Metadata tools parse files that can be untrusted. Keep bundled and installed tools
up to date; pin and test replacements in the release dependency files. Media
scanning and exporting run locally; the app has no upload or telemetry feature.

Reports preserve raw metadata and absolute paths. They may expose recording dates,
GPS positions, names and device identifiers. Share only sanitized reports. CSV
exports neutralize common spreadsheet formula prefixes; JSON retains original values.

For a suspected credential exposure or vulnerability, avoid posting the secret or
private report in a public issue. Use GitHub's private vulnerability reporting if
it is enabled for this repository. Maintainers should enable it before publication.
