from datetime import datetime, timezone

from app.core.timestamp_resolver import parse_timestamp, resolve_timestamp


def test_recording_timestamp_beats_filesystem_copy_dates():
    selected, candidates, warnings = resolve_timestamp(
        {"DateTimeOriginal": "2024:02:03 04:05:06", "CreateDate": "2024:02:03 04:05:06"},
        filesystem_created=datetime(2026, 1, 1, tzinfo=timezone.utc),
        now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert selected.source == "DateTimeOriginal"
    assert len(candidates) == 3
    assert not warnings


def test_quicktime_offset_normalized_to_utc():
    assert parse_timestamp("2026-08-12T12:30:00+02:00") == datetime(2026, 8, 12, 10, 30, tzinfo=timezone.utc)


def test_unset_clock_is_flagged_but_retained():
    selected, candidates, warnings = resolve_timestamp({"CreateDate": "1999:01:01 00:00:00"},
                                                        now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert selected is not None
    assert selected.normalized.year == 1999
    assert any("unset camera clock" in item.lower() for item in selected.warnings)
    assert warnings


def test_conflicting_metadata_kept_and_warned():
    selected, candidates, warnings = resolve_timestamp(
        {"DateTimeOriginal": "2024:02:03 04:05:06", "CreateDate": "2020:02:03 04:05:06"},
        now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert selected.source == "DateTimeOriginal"
    assert len(candidates) == 2
    assert any("conflict" in item for item in warnings)


def test_filename_date_is_fallback():
    selected, candidates, _ = resolve_timestamp({}, "CAM_20260812_123045.mov",
                                                  now=datetime(2026, 8, 13, tzinfo=timezone.utc))
    assert selected.source == "filename"
