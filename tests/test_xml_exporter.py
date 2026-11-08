from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pytest

from app.core.xml_exporter import write_timeline_xml
from app.models.video_file import TimestampCandidate, VideoFile


def clip(name, rate=25, duration=2, audio=True):
    return VideoFile('/media/' + name, name, 100, duration_seconds=duration,
                     width=1920, height=1080, frame_rate=rate,
                     audio_codec='aac' if audio else None,
                     metadata={'ffprobe.audio_channels': 2, 'ffprobe.audio_sample_rate': 48000})


def test_linked_assembly_paths_order_exclusion_and_mixed_rates(tmp_path):
    first = clip('café & one.mov')
    first.selected_timestamp = TimestampCandidate('test', '', datetime(2026, 1, 1, tzinfo=timezone.utc), 1)
    second = clip('second.mov', 30000 / 1001, 1)
    excluded = clip('excluded.mov')
    path = tmp_path / 'timeline.xml'
    write_timeline_xml(path, [second, excluded, first], excluded_paths=[excluded.path])
    root = ET.parse(path).getroot()
    items = root.findall('./sequence/media/video/track/clipitem')
    assert [item.findtext('name') for item in items] == [first.filename, second.filename]
    assert items[0].findtext('file/pathurl') == 'file:///media/caf%C3%A9%20%26%20one.mov'
    assert [(item.findtext('start'), item.findtext('end')) for item in items] == [('0', '50'), ('50', '75')]
    assert items[1].findtext('out') == '30'
    assert items[1].findtext('rate/ntsc') == 'TRUE'
    assert len(root.findall('./sequence/media/audio/track/clipitem')) == 4
    ids = {item.attrib['id'] for item in root.findall('.//clipitem')}
    assert all(link.text in ids for link in root.findall('.//linkclipref'))
    assert root.findtext('./sequence/duration') == '75'


def test_missing_metadata_does_not_overwrite_existing_xml(tmp_path):
    path = tmp_path / 'timeline.xml'
    path.write_text('keep')
    bad = clip('bad.mov')
    bad.duration_seconds = None
    with pytest.raises(ValueError, match='duration'):
        write_timeline_xml(path, [bad])
    assert path.read_text() == 'keep'
    with pytest.raises(ValueError, match='Include'):
        write_timeline_xml(path, [bad], excluded_paths=[bad.path])


def test_audio_requires_channel_metadata(tmp_path):
    video = clip('old-session.mov')
    video.metadata = {}
    with pytest.raises(ValueError, match='rescan'):
        write_timeline_xml(tmp_path / 'timeline.xml', [video])


def test_video_only_and_fractional_timing(tmp_path):
    path = tmp_path / 'timeline.xml'
    videos = [clip(str(i)+'.mov', 24000/1001, 1, audio=False) for i in range(100)]
    write_timeline_xml(path, videos)
    root = ET.parse(path).getroot()
    assert root.findtext('./sequence/duration') == '2400'
    assert not root.findall('./sequence/media/audio/track')


def test_nonstandard_average_rate_is_explicitly_rejected(tmp_path):
    with pytest.raises(ValueError, match='Unsupported frame rate'):
        write_timeline_xml(tmp_path / 'timeline.xml', [clip('variable.mov', 12.457627118644067)])
