"""Stable chronological ordering with unknown timestamps placed last."""
from app.models.video_file import VideoFile


def chronological_sort(videos):
    return sorted(videos, key=lambda v: (
        v.selected_timestamp is None or v.selected_timestamp.normalized is None,
        v.selected_timestamp.normalized if v.selected_timestamp and v.selected_timestamp.normalized else None,
        v.filename.casefold(), v.path.casefold()))
