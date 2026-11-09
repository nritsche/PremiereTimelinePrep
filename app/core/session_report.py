"""Export reviewed footage without changing media files."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile

from app.core.chronological_sorter import chronological_sort
from app.core.output_safety import check_output_path


def write_session_report(path, videos, *, excluded_paths=(), folders=()):
    """Atomically write a JSON audit report or a chronological CSV inventory.

    Reports include every scanned clip; inclusion is explicit and independent of
    the current search/filter. JSON retains original candidates and raw metadata.
    """
    videos = list(videos)
    check_output_path(path, videos)
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
                    writer.writerow([_csv_cell(value) for value in [
                        video.path not in excluded, video.path, video.filename, video.camera,
                        stamp.normalized.astimezone(timezone.utc).isoformat() if stamp and stamp.normalized else "",
                        video.duration_seconds, video.width, video.height, video.frame_rate,
                        stamp.source if stamp else "", stamp.confidence if stamp else "",
                        " | ".join(dict.fromkeys(video.warnings + (stamp.warnings if stamp else []))),
                        video.error,
                    ]])
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _csv_cell(value):
    # Quoting alone does not stop spreadsheet formula interpretation.
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def _reject_constant(value):
    raise ValueError("Session contains a non-finite number: {}".format(value))


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
        if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
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
        if Path(path).stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Session exceeds the 64 MB size limit")
        with open(path, encoding="utf-8") as stream:
            payload = json.load(stream, parse_constant=_reject_constant)
        if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
            raise ValueError("Unsupported session version")
        folders = payload["folders"]
        if not isinstance(folders, list) or not all(isinstance(folder, str) for folder in folders):
            raise ValueError("Invalid session folders")
        if not isinstance(payload["videos"], list):
            raise ValueError("Invalid session clip list")
        if len(payload["videos"]) > 50000:
            raise ValueError("Session exceeds the 50,000 clip limit")
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
            for field in ("path", "filename"):
                if "\x00" in values[field]:
                    raise ValueError("Invalid null character in clip {}".format(field))
            if type(values.get("size_bytes")) is not int or values["size_bytes"] < 0:
                raise ValueError("Invalid clip size")
            for field in ("duration_seconds", "frame_rate"):
                number = values.get(field)
                if number is not None and (type(number) not in (int, float) or not math.isfinite(number) or number <= 0):
                    raise ValueError("Invalid {}".format(field))
            for field in ("width", "height"):
                number = values.get(field)
                if number is not None and (type(number) is not int or number <= 0):
                    raise ValueError("Invalid {}".format(field))
            for field in ("video_codec", "audio_codec", "error"):
                if values.get(field) is not None and not isinstance(values[field], str):
                    raise ValueError("Invalid {}".format(field))
            if not isinstance(values.get("metadata", {}), dict):
                raise ValueError("Invalid clip metadata")
            metadata = values.get("metadata", {})
            if not isinstance(metadata.get("assumed_timezone", "UTC"), str):
                raise ValueError("Invalid camera timezone")
            for field in ("ffprobe.avg_frame_rate", "ffprobe.r_frame_rate"):
                if metadata.get(field) is not None and not isinstance(metadata[field], str):
                    raise ValueError("Invalid metadata rate")
            channels = metadata.get("ffprobe.audio_channels")
            if channels is not None and (type(channels) is not int or not 1 <= channels <= 32):
                raise ValueError("Invalid audio channel count")
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
