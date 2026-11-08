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


def read_session_report(path):
    """Load a versioned JSON session without probing or changing its media."""
    from app.models.video_file import TimestampCandidate, VideoFile

    def timestamp(value):
        if value is None:
            return None
        value = dict(value)
        if not isinstance(value.get("source"), str) or not isinstance(value.get("raw_value"), str):
            raise ValueError("Invalid timestamp source or raw value")
        confidence = value.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("Invalid timestamp confidence")
        if not isinstance(value.get("warnings"), list) or not all(isinstance(item, str) for item in value["warnings"]):
            raise ValueError("Invalid timestamp warnings")
        value["normalized"] = instant(value.get("normalized"))
        return TimestampCandidate(**value)

    def instant(value):
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Session timestamps must include a timezone")
        return parsed.astimezone(timezone.utc)

    try:
        with open(path, encoding="utf-8") as stream:
            payload = json.load(stream)
        if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
            raise ValueError("Unsupported session version")
        folders = payload["folders"]
        if not isinstance(folders, list) or not all(isinstance(folder, str) for folder in folders):
            raise ValueError("Invalid session folders")
        if not isinstance(payload["videos"], list):
            raise ValueError("Invalid session clip list")
        videos, excluded, seen = [], set(), set()
        for entry in payload["videos"]:
            values = dict(entry)
            included = values.pop("included")
            if type(included) is not bool:
                raise ValueError("Invalid clip inclusion flag")
            if not isinstance(values.get("path"), str) or not values["path"] or values["path"] in seen:
                raise ValueError("Invalid or duplicate clip path")
            seen.add(values["path"])
            if not isinstance(values.get("filename"), str):
                raise ValueError("Invalid clip filename")
            if values.get("camera") is not None and not isinstance(values["camera"], str):
                raise ValueError("Invalid camera source")
            values["selected_timestamp"] = timestamp(values.get("selected_timestamp"))
            if not isinstance(values["timestamp_candidates"], list) or any(item is None for item in values["timestamp_candidates"]):
                raise ValueError("Invalid timestamp candidates")
            values["timestamp_candidates"] = [timestamp(item) for item in values["timestamp_candidates"]]
            for field in ("filesystem_created", "filesystem_modified"):
                values[field] = instant(values.get(field))
            for field in ("warnings",):
                if not isinstance(values[field], list) or not all(isinstance(item, str) for item in values[field]):
                    raise ValueError("Invalid clip warnings")
            video = VideoFile(**values)
            videos.append(video)
            if not included:
                excluded.add(video.path)
        return videos, excluded, folders
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Invalid session report: {}".format(exc)) from exc
