"""Export reviewed footage without changing media files."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from app.core.chronological_sorter import chronological_sort


def write_session_report(path, videos, *, excluded_paths=(), folders=()):
    """Atomically write a JSON audit report or a chronological CSV inventory.

    Reports include every scanned clip; inclusion is explicit and independent of
    the current search/filter. JSON retains original candidates and raw metadata.
    """
    path = Path(path)
    if path.suffix.lower() not in {".json", ".csv"}:
        raise ValueError("Choose a .json or .csv report filename")
    excluded = set(excluded_paths)
    ordered = chronological_sort(videos)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as stream:
            temporary = stream.name
            if path.suffix.lower() == ".json":
                payload = {
                    "schema_version": 1,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "folders": list(folders),
                    "videos": [dict(asdict(video), included=video.path not in excluded)
                               for video in ordered],
                }
                json.dump(payload, stream, ensure_ascii=False, indent=2,
                          default=_json_default, allow_nan=False)
                stream.write("\n")
            else:
                writer = csv.writer(stream)
                writer.writerow(["included", "path", "filename", "camera", "capture_time_utc",
                                 "duration_seconds", "width", "height", "frame_rate",
                                 "timestamp_source", "confidence", "warnings", "error"])
                for video in ordered:
                    stamp = video.selected_timestamp
                    writer.writerow([
                        video.path not in excluded, video.path, video.filename, video.camera,
                        stamp.normalized.astimezone(timezone.utc).isoformat() if stamp and stamp.normalized else "",
                        video.duration_seconds, video.width, video.height, video.frame_rate,
                        stamp.source if stamp else "", stamp.confidence if stamp else "",
                        " | ".join(dict.fromkeys(video.warnings + (stamp.warnings if stamp else []))),
                        video.error,
                    ])
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("Cannot serialize {}".format(type(value).__name__))
