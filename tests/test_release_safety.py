"""Regression tests for public release audit findings."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

import pytest

from app.core.metadata_extractor import ScanCancelled, _run_json, extract_video
from app.core.session_report import read_session_report, write_session_report
from app.core.timestamp_resolver import parse_timestamp, resolve_timestamp
from app.core.xml_exporter import write_timeline_xml
from app.models.video_file import VideoFile


def test_grouped_embedded_recording_date_beats_filename_and_filesystem():
    selected, _, _ = resolve_timestamp(
        {'ExifIFD:DateTimeOriginal': '2024:02:03 04:05:06'}, 'CAM_20260812_123045.mov',
        filesystem_modified=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert selected.source == 'ExifIFD:DateTimeOriginal'
    assert selected.normalized.year == 2024
    assert selected.confidence == .98


@pytest.mark.parametrize('value', ['2024:02:30 04:05:06', 'CAM_20240230_040506.mov', '2024:01:01 99:00:00'])
def test_malformed_dates_are_retained_without_raising(value):
    assert parse_timestamp(value) is None
    selected, candidates, _ = resolve_timestamp({'ExifIFD:DateTimeOriginal': value, 'CreateDate': '2024:01:02 00:00:00'})
    assert selected.source == 'CreateDate'
    assert candidates[0].warnings


@pytest.mark.parametrize('field,value', [
    ('duration_seconds', 'oops'), ('duration_seconds', -1), ('duration_seconds', float('nan')),
    ('frame_rate', True), ('frame_rate', float('inf')), ('width', -1), ('height', '1080'),
    ('size_bytes', -1), ('metadata', []), ('error', {}), ('path', '/bad\x00.mov'),
])
def test_invalid_session_rejected_before_gui(field, value, tmp_path):
    path = tmp_path / 'session.json'
    write_session_report(path, [VideoFile('/missing.mov', 'missing.mov', 1)])
    data = json.loads(path.read_text(encoding='utf-8'))
    data['videos'][0][field] = value
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        read_session_report(path)


@pytest.mark.parametrize('kind', ['json', 'xml'])
def test_export_cannot_overwrite_source_or_hardlink(kind, tmp_path):
    original = tmp_path / ('source.' + kind)
    original.write_bytes(b'precious media')
    video = VideoFile(str(original), original.name, 14)
    writer = write_timeline_xml if kind == 'xml' else write_session_report
    with pytest.raises(ValueError, match='source media'):
        writer(original, [video])
    alias = tmp_path / ('alias.' + kind)
    try:
        alias.hardlink_to(original)
    except OSError:
        pytest.skip('Hard links unavailable')
    with pytest.raises(ValueError, match='source media'):
        writer(alias, [video])
    assert original.read_bytes() == b'precious media'


def test_csv_neutralizes_formulas(tmp_path):
    import csv
    path = tmp_path / 'report.csv'
    write_session_report(path, [VideoFile('/a.mov', '=1+1', 1, camera='@SUM(1,2)')])
    with path.open(encoding='utf-8', newline='') as stream:
        row = next(csv.DictReader(stream))
    assert row['filename'] == "'=1+1"
    assert row['camera'].startswith("'@")


def test_metadata_process_cancels_and_times_out_promptly():
    command = [sys.executable, '-c', 'import time; time.sleep(30)']
    start = time.monotonic()
    with pytest.raises(ScanCancelled):
        _run_json(command, cancelled=lambda: time.monotonic() - start > .2)
    assert time.monotonic() - start < 5
    with pytest.raises(TimeoutError):
        _run_json(command, timeout=.2)


def test_metadata_keeps_stream_dates_and_uses_camera_timezone(monkeypatch, tmp_path):
    from zoneinfo import ZoneInfo
    import app.core.metadata_extractor as module
    path = tmp_path / 'clip.mov'
    path.write_bytes(b'dummy')
    data = {'streams': [{'index': 0, 'codec_type': 'video', 'codec_name': 'h264', 'width': 1920,
                        'height': 1080, 'avg_frame_rate': '0/0', 'r_frame_rate': '25/1',
                        'tags': {'creation_time': '2024-07-01T12:00:00'}}], 'format': {'duration': '2'}}
    monkeypatch.setattr(module, '_run_json', lambda command, **kwargs: data if '-show_streams' in command else [])
    video = extract_video(str(path), ffprobe='ffprobe', exiftool='exiftool', default_timezone=ZoneInfo('Europe/Madrid'))
    assert video.frame_rate == 25
    assert video.selected_timestamp.normalized.hour == 10
    assert video.metadata['ffprobe.streams'] == data['streams']
    assert video.metadata['assumed_timezone'] == 'Europe/Madrid'


@pytest.mark.parametrize('stream,extra', [
    ({'tags': {'rotate': '90'}}, []),
    ({'field_order': 'tt'}, []),
    ({'sample_aspect_ratio': '4:3'}, []),
    ({'start_time': '2'}, []),
    ({}, [{'codec_type': 'audio'}, {'codec_type': 'audio'}]),
])
def test_unsupported_media_cannot_silently_export(stream, extra, tmp_path):
    video = VideoFile(str(tmp_path / 'clip.mov'), 'clip.mov', 1, duration_seconds=2,
                      width=1920, height=1080, frame_rate=25)
    video.metadata['ffprobe.streams'] = [dict(codec_type='video', **stream)] + extra
    with pytest.raises(ValueError, match='does not yet support'):
        write_timeline_xml(tmp_path / 'timeline.xml', [video])


def test_scanner_cancellation_and_missing_directory(tmp_path):
    from app.core.scanner import discover_videos
    (tmp_path / 'clip.mov').write_bytes(b'dummy')
    assert list(discover_videos([str(tmp_path)], cancelled=lambda: True)) == []
    errors = []
    assert list(discover_videos([str(tmp_path / 'missing')], on_error=errors.append)) == []
    assert errors


def test_attached_picture_is_not_selected_as_primary_video(monkeypatch, tmp_path):
    import app.core.metadata_extractor as module
    media = tmp_path / 'clip.mov'
    media.write_bytes(b'dummy')
    cover = {'codec_type': 'video', 'codec_name': 'mjpeg', 'width': 10, 'height': 10,
             'disposition': {'attached_pic': 1}}
    primary = {'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080,
               'avg_frame_rate': '25/1'}
    monkeypatch.setattr(module, '_run_json', lambda command, **kwargs:
                        {'streams': [cover, primary], 'format': {'duration': '2'}} if '-show_streams' in command else [])
    video = extract_video(str(media), ffprobe='ffprobe', exiftool='exiftool')
    assert video.width == 1920
    assert video.video_codec == 'h264'


def test_unknown_timezone_metadata_rejected(tmp_path):
    path = tmp_path / 'session.json'
    write_session_report(path, [VideoFile('/a.mov', 'a.mov', 1, metadata={'assumed_timezone': []})])
    with pytest.raises(ValueError, match='timezone'):
        read_session_report(path)
