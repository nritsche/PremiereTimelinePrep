"""FFprobe and ExifTool adapters. Either tool may be missing or fail per file."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.core.timestamp_resolver import resolve_timestamp
from app.models.video_file import VideoFile


EXIF_FIELDS = ["DateTimeOriginal", "SubSecDateTimeOriginal", "CreateDate", "MediaCreateDate",
               "TrackCreateDate", "CreationTime", "QuickTime:CreateDate",
               "QuickTime:MediaCreateDate", "QuickTime:TrackCreateDate"]


def _bundled_tool(name: str) -> Optional[str]:
    """Find a tool embedded by PyInstaller, including one-file extraction dirs."""
    roots = []
    if getattr(sys, "_MEIPASS", None):
        roots.append(sys._MEIPASS)
    roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    filename = name + (".exe" if os.name == "nt" else "")
    for root in roots:
        path = os.path.join(root, "tools", name, filename)
        if os.path.isfile(path):
            return path
    return None


def _run_json(command: list, timeout: int = 45) -> Dict[str, Any]:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, check=False, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "process exited with code {}".format(result.returncode))
    return json.loads(result.stdout or "{}")


def extract_video(path: str, ffprobe: Optional[str] = None, exiftool: Optional[str] = None) -> VideoFile:
    """Inspect one file. Metadata-tool failures are recorded without aborting a scan."""
    stat = os.stat(path)
    video = VideoFile(path=os.path.abspath(path), filename=os.path.basename(path), size_bytes=stat.st_size)
    video.filesystem_created = datetime.fromtimestamp(getattr(stat, "st_birthtime", stat.st_ctime), timezone.utc)
    video.filesystem_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    ffprobe = ffprobe or _bundled_tool("ffprobe") or shutil.which("ffprobe")
    exiftool = exiftool or _bundled_tool("exiftool") or shutil.which("exiftool")
    ff_data: Dict[str, Any] = {}
    exif_data: Dict[str, Any] = {}
    if ffprobe:
        try:
            ff_data = _run_json([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", path])
        except Exception as exc:
            video.warnings.append("FFprobe: {}".format(exc))
    else:
        video.warnings.append("FFprobe was not found; technical media details are unavailable")
    if exiftool:
        try:
            result = subprocess.run([exiftool, "-j", "-G1", "-a", "-s", path], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=45, check=False, text=True,
                                    encoding="utf-8", errors="replace")
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "process exited with code {}".format(result.returncode))
            records = json.loads(result.stdout or "[]")
            exif_data = records[0] if records else {}
        except Exception as exc:
            video.warnings.append("ExifTool: {}".format(exc))
    else:
        video.warnings.append("ExifTool was not found; embedded timestamp details may be incomplete")

    streams = ff_data.get("streams", [])
    for stream in streams:
        if stream.get("codec_type") == "video" and video.video_codec is None:
            video.video_codec = stream.get("codec_name")
            video.width, video.height = stream.get("width"), stream.get("height")
            rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
            try:
                numerator, denominator = rate.split("/")
                video.frame_rate = float(numerator) / float(denominator) if float(denominator) else None
            except (ValueError, AttributeError, ZeroDivisionError):
                pass
        elif stream.get("codec_type") == "audio" and video.audio_codec is None:
            video.audio_codec = stream.get("codec_name")
        tags = stream.get("tags", {})
        video.metadata.update({"ffprobe.stream.{}".format(k): v for k, v in tags.items()})
    try:
        video.duration_seconds = float(ff_data.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        pass
    format_tags = ff_data.get("format", {}).get("tags", {})
    timestamp_values: Dict[str, Any] = {}
    for key, value in format_tags.items():
        clean = key.split(":")[-1]
        if clean in EXIF_FIELDS or clean.lower() in ("creation_time", "creationtime"):
            timestamp_values[clean] = value
    # ExifTool's grouped keys are retained verbatim in metadata and mapped to a
    # canonical candidate name without throwing away duplicate tag occurrences.
    for key, value in exif_data.items():
        if key == "SourceFile":
            continue
        video.metadata["exiftool." + key] = value
        clean = key.split(":")[-1]
        if clean in EXIF_FIELDS or clean in ("CreationTime", "DateTimeOriginal"):
            timestamp_values[key if ":" in key else clean] = value
    make = exif_data.get("Make") or exif_data.get("QuickTime:Make")
    model = exif_data.get("Model") or exif_data.get("QuickTime:Model")
    video.camera = " ".join(str(x).strip() for x in (make, model) if x) or None
    video.metadata["exiftool.raw"] = exif_data
    selected, candidates, warnings = resolve_timestamp(timestamp_values, video.filename,
                                                       video.filesystem_created, video.filesystem_modified)
    video.selected_timestamp = selected
    video.timestamp_candidates = candidates
    video.warnings.extend(warnings)
    if not selected:
        video.warnings.append("No usable capture timestamp found")
    return video
