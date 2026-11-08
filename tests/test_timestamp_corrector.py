from datetime import datetime, timedelta, timezone

from app.core.timestamp_corrector import apply_offset, override_timestamp, set_reference_time
from app.models.video_file import TimestampCandidate, VideoFile


def make(path, camera, stamp):
    video = VideoFile(path, path, 1, camera=camera)
    video.selected_timestamp = TimestampCandidate("CreateDate", stamp.isoformat(), stamp, 0.9)
    return video


def test_reference_adjusts_camera_and_keeps_relative_order():
    first = make("a", "A", datetime(1999, 1, 1, tzinfo=timezone.utc))
    second = make("b", "A", datetime(1999, 1, 1, 0, 0, 5, tzinfo=timezone.utc))
    unrelated = make("c", "B", datetime(1999, 1, 1, tzinfo=timezone.utc))
    delta = set_reference_time([first, second, unrelated], first,
                               datetime(2026, 8, 12, tzinfo=timezone.utc))
    assert first.selected_timestamp.normalized == datetime(2026, 8, 12, tzinfo=timezone.utc)
    assert second.selected_timestamp.normalized - first.selected_timestamp.normalized == timedelta(seconds=5)
    assert unrelated.selected_timestamp.normalized.year == 1999
    assert delta.days > 9000


def test_individual_override():
    video = make("a", "A", datetime(1999, 1, 1, tzinfo=timezone.utc))
    override_timestamp(video, datetime(2026, 8, 12, tzinfo=timezone.utc))
    assert video.selected_timestamp.source == "user_override"
