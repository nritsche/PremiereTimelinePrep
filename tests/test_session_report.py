import csv
from datetime import datetime, timedelta, timezone
import json

import pytest

from app.core.session_report import write_session_report
from app.core.timestamp_corrector import apply_offset
from app.models.video_file import TimestampCandidate, VideoFile


def test_reports_preserve_original_candidates_and_export_corrected_order(tmp_path):
    original = TimestampCandidate("embedded", "original", datetime(2026, 1, 1, tzinfo=timezone.utc), .8)
    clip = VideoFile("/media/café.mov", "café.mov", 100, timestamp_candidates=[original],
                     selected_timestamp=original, warnings=["Review timezone"])
    unknown = VideoFile("/media/unknown.mov", "unknown.mov", 50)
    apply_offset(clip, timedelta(hours=1))
    path = tmp_path / "report.json"
    write_session_report(path, [unknown, clip], excluded_paths=[clip.path], folders=["/media"])
    report = json.loads(path.read_text())
    assert report["folders"] == ["/media"]
    first, last = report["videos"]
    assert first["included"] is False
    assert last["included"] is True
    assert first["timestamp_candidates"][0]["normalized"] == "2026-01-01T00:00:00+00:00"
    assert first["selected_timestamp"]["normalized"] == "2026-01-01T01:00:00+00:00"
    path = tmp_path / "report.csv"
    write_session_report(path, [unknown, clip], excluded_paths=[clip.path])
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["filename"] == "café.mov"
    assert rows[0]["included"] == "False"
    assert "User-applied offset" in rows[0]["warnings"]
    assert rows[1]["capture_time_utc"] == ""


def test_failed_export_preserves_existing_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("previous report")
    clip = VideoFile("/clip.mov", "clip.mov", 1, metadata={"unsupported": object()})
    with pytest.raises(TypeError):
        write_session_report(path, [clip])
    assert path.read_text() == "previous report"
    assert list(tmp_path.iterdir()) == [path]
