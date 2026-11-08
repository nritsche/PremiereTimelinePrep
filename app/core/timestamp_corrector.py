"""In-memory timestamp correction primitives, independent of the GUI."""
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from app.models.video_file import TimestampCandidate, VideoFile


def apply_offset(video: VideoFile, offset: timedelta) -> None:
    """Apply a correction while preserving the original selection for audit."""
    current = video.selected_timestamp
    if not current or not current.normalized:
        return
    corrected = current.normalized + offset
    video.selected_timestamp = TimestampCandidate(
        source="user_offset({})".format(current.source), raw_value=current.raw_value,
        normalized=corrected, confidence=1.0,
        warnings=list(current.warnings) + ["User-applied offset: {} seconds".format(offset.total_seconds())])


def set_reference_time(videos: Iterable[VideoFile], reference: VideoFile, actual_time: datetime) -> timedelta:
    """Set one clip's actual time and apply the resulting offset to its camera group."""
    if not reference.selected_timestamp or not reference.selected_timestamp.normalized:
        raise ValueError("Reference video has no selected capture timestamp")
    if actual_time.tzinfo is None:
        actual_time = actual_time.replace(tzinfo=timezone.utc)
    delta = actual_time.astimezone(timezone.utc) - reference.selected_timestamp.normalized
    group = reference.camera
    for video in videos:
        if video is reference or (group is not None and video.camera == group):
            apply_offset(video, delta)
    return delta


def override_timestamp(video: VideoFile, actual_time: datetime) -> None:
    if actual_time.tzinfo is None:
        actual_time = actual_time.replace(tzinfo=timezone.utc)
    previous = video.selected_timestamp
    video.selected_timestamp = TimestampCandidate(
        source="user_override", raw_value=actual_time.isoformat(),
        normalized=actual_time.astimezone(timezone.utc), confidence=1.0,
        warnings=list(previous.warnings) if previous else [])
