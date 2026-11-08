"""Flag timestamp patterns that deserve human review; never remove candidates."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from app.models.video_file import VideoFile


def detect_anomalies(videos: Iterable[VideoFile], now: datetime = None) -> List[str]:
    issues: List[str] = []
    rows = list(videos)
    now = now or datetime.now(timezone.utc)
    by_camera = {}
    by_stamp = Counter()
    for video in rows:
        stamp = video.selected_timestamp
        if not stamp or not stamp.normalized:
            continue
        by_stamp[(video.camera or "Unknown source", stamp.normalized)] += 1
        by_camera.setdefault(video.camera or "Unknown source", []).append((video, stamp.normalized))
        if stamp.normalized.year == 1999 and stamp.normalized.month == 1 and stamp.normalized.day == 1:
            issues.append("{}: likely unset 1999-01-01 camera clock".format(video.filename))
        if stamp.normalized > now.astimezone(timezone.utc) + timedelta(days=365):
            issues.append("{}: timestamp is more than one year in the future".format(video.filename))
        if video.warnings:
            issues.extend("{}: {}".format(video.filename, warning) for warning in video.warnings)
    for camera, items in by_camera.items():
        if len(items) > 1:
            items.sort(key=lambda item: item[1])
            for (left, first), (right, second) in zip(items, items[1:]):
                if (second - first).total_seconds() > 12 * 3600:
                    issues.append("{}: large timestamp gap within source {} before {}".format(right.filename, camera, right.filename))
    return list(dict.fromkeys(issues))
