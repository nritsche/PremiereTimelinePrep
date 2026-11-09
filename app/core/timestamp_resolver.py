"""Timestamp candidate parsing and deterministic, reviewable selection rules."""
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from app.models.video_file import TimestampCandidate


# Higher values represent stronger evidence. Filesystem timestamps are weak because
# copying media commonly changes them. QuickTime values are treated as wall clock
# values unless they carry an explicit offset; camera conventions vary.
FIELD_CONFIDENCE = {
    "DateTimeOriginal": 0.98,
    "SubSecDateTimeOriginal": 0.98,
    "CreateDate": 0.88,
    "MediaCreateDate": 0.84,
    "TrackCreateDate": 0.80,
    "CreationTime": 0.76,
    "QuickTime:CreateDate": 0.86,
    "QuickTime:MediaCreateDate": 0.82,
    "QuickTime:TrackCreateDate": 0.78,
    "filename": 0.58,
    "filesystem_created": 0.24,
    "filesystem_modified": 0.16,
}

_DATE_PATTERNS = (
    re.compile(r"(?P<y>20\d{2}|19\d{2})[-_]?(?P<m>\d{2})[-_]?(?P<d>\d{2})[ T_-]?(?P<h>\d{2})[-:]?(?P<mi>\d{2})[-:]?(?P<s>\d{2})(?:[.,](?P<f>\d+))?(?P<z>Z|[+-]\d{2}:?\d{2})?"),
)


def _parse_timestamp(raw: object, default_timezone: timezone = timezone.utc) -> Optional[datetime]:
    """Parse common ExifTool/QuickTime/filename date forms; return aware UTC."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value or value.startswith("0000:00:00"):
        return None
    normalized = value.replace("Z", "+00:00")
    # ExifTool commonly uses YYYY:MM:DD HH:MM:SS[.fraction][+/-HH:MM].
    m = re.match(r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$", value)
    if m:
        y, mo, d, h, mi, sec = map(int, m.groups()[:6])
        frac, zone = m.group(7), m.group(8)
        micros = int(float(frac or 0) * 1000000)
        dt = datetime(y, mo, d, h, mi, sec, micros)
        if zone:
            z = zone
            if z != "Z" and len(z) == 5 and ":" not in z:
                z = z[:3] + ":" + z[3:]
            dt = dt.replace(tzinfo=datetime.fromisoformat("2000-01-01T00:00:00" + ("+00:00" if z == "Z" else z)).tzinfo)
        else:
            dt = dt.replace(tzinfo=default_timezone)
        return dt.astimezone(timezone.utc)
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_timezone)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for pattern in _DATE_PATTERNS:
        match = pattern.search(value)
        if match:
            parts = match.groupdict()
            zone = parts["z"]
            text = "{}-{}-{}T{}:{}:{}{}".format(parts["y"], parts["m"], parts["d"], parts["h"], parts["mi"], parts["s"], ("." + parts["f"] if parts["f"] else ""))
            if zone:
                text += zone if zone == "Z" or ":" in zone else zone[:3] + ":" + zone[3:]
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=default_timezone)
            return dt.astimezone(timezone.utc)
    return None


def parse_timestamp(raw: object, default_timezone: timezone = timezone.utc) -> Optional[datetime]:
    """Malformed camera dates are reviewable candidates, never scan failures."""
    try:
        return _parse_timestamp(raw, default_timezone)
    except (ValueError, OverflowError, TypeError):
        return None


def canonical_source(source):
    """Rank a grouped tag without discarding its original provenance."""
    name = source.rsplit(":", 1)[-1]
    aliases = {"creation_time": "CreationTime", "creationtime": "CreationTime"}
    return aliases.get(name.lower(), name)


def candidate(source: str, raw: object, confidence: Optional[float] = None,
              default_timezone: timezone = timezone.utc) -> TimestampCandidate:
    text = str(raw)
    parsed = parse_timestamp(raw, default_timezone)
    warnings: List[str] = []
    if parsed is None:
        warnings.append("Timestamp could not be parsed")
    if parsed and parsed.month == 1 and parsed.day == 1 and parsed.year in (1999, 2000):
        warnings.append("Possible unset camera clock (January 1 sentinel date)")
    if parsed and (parsed.year < 1990 or parsed.year > 2100):
        warnings.append("Timestamp is outside the expected 1990–2100 range")
    return TimestampCandidate(source, text, parsed, confidence if confidence is not None else FIELD_CONFIDENCE.get(canonical_source(source), 0.5), warnings)


def resolve_timestamp(values: Dict[str, object], filename: str = "", filesystem_created: Optional[datetime] = None,
                      filesystem_modified: Optional[datetime] = None, now: Optional[datetime] = None,
                      default_timezone: timezone = timezone.utc) -> Tuple[Optional[TimestampCandidate], List[TimestampCandidate], List[str]]:
    """Return selected candidate, every parseable/raw candidate, and review warnings.

    Strong embedded recording fields win over generic creation fields. Conflicting
    embedded values are retained and surfaced. We never discard a suspicious date.
    """
    candidates: List[TimestampCandidate] = []
    for key, value in values.items():
        if value in (None, ""):
            continue
        # Preserve lists/arrays as separate candidates with the same field source.
        for item in value if isinstance(value, (list, tuple)) else [value]:
            candidates.append(candidate(key, item, default_timezone=default_timezone))
    for match in _DATE_PATTERNS:
        found = match.search(filename)
        if found:
            candidates.append(candidate("filename", found.group(0), default_timezone=default_timezone))
            break
    for source, value in (("filesystem_created", filesystem_created), ("filesystem_modified", filesystem_modified)):
        if value:
            candidates.append(candidate(source, value.isoformat(), default_timezone=timezone.utc))

    valid = [c for c in candidates if c.normalized]
    # Ranking uses explicit field priority, then configured confidence.
    order = {name: index for index, name in enumerate(FIELD_CONFIDENCE)}
    selected = min(valid, key=lambda c: (order.get(canonical_source(c.source), 999), -c.confidence)) if valid else None
    warnings: List[str] = []
    embedded = [c for c in valid if c.source not in ("filename", "filesystem_created", "filesystem_modified")]
    if selected:
        if selected.source in ("filesystem_created", "filesystem_modified"):
            warnings.append("Recording date is based on a filesystem time; copying files may change it")
        instant = selected.normalized
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if instant < datetime(1990, 1, 1, tzinfo=timezone.utc) or instant > reference + timedelta(days=365):
            warnings.append("Selected timestamp is significantly in the past or future")
        if any("unset camera clock" in w for w in selected.warnings):
            warnings.append("Selected timestamp may come from an unset camera clock")
    if len(embedded) > 1:
        stamps = [c.normalized for c in embedded]
        if (max(stamps) - min(stamps)).total_seconds() > 86400:
            warnings.append("Embedded timestamp fields conflict by more than 24 hours")
    return selected, candidates, warnings
