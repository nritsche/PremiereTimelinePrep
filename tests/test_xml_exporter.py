from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from app.core.xml_exporter import write_timeline_xml
from app.models.video_file import TimestampCandidate, VideoFile


def clip(name, rate=25, duration=2, audio=True):
    return VideoFile(str(Path('media', name).resolve()), name, 100, duration_seconds=duration,
                     width=1920, height=1080, frame_rate=rate,
                     audio_codec='aac' if audio else None,
                     metadata={'ffprobe.audio_channels': 2, 'ffprobe.audio_sample_rate': 48000,
                               'ffprobe.streams': [{'codec_type': 'video'}]})


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
    assert items[0].findtext('file/pathurl') == Path(first.path).as_uri()
    assert items[0].findtext('file/pathurl').endswith('/caf%C3%A9%20%26%20one.mov')
    assert [(item.findtext('start'), item.findtext('end')) for item in items] == [('0', '50'), ('50', '75')]
    assert items[1].findtext('out') == '30'
    assert items[1].findtext('rate/ntsc') == 'TRUE'
    assert len(root.findall('./sequence/media/audio/track/clipitem')) == 4
    ids = {item.attrib['id'] for item in root.findall('.//clipitem')}
    assert all(link.text in ids for link in root.findall('.//linkclipref'))
    assert root.findtext('./sequence/duration') == '75'


def test_missing_metadata_does_not_overwrite_existing_xml(tmp_path):
    path = tmp_path / 'timeline.xml'
    path.write_text('keep', encoding='utf-8')
    bad = clip('bad.mov')
    bad.duration_seconds = None
    with pytest.raises(ValueError, match='duration'):
        write_timeline_xml(path, [bad])
    assert path.read_text(encoding='utf-8') == 'keep'
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
    assert root.findtext('./sequence/duration') == '2398'
    assert not root.findall('./sequence/media/audio/track')


def test_nonstandard_rates_are_disclosed_and_preserve_elapsed_time(tmp_path):
    from app.core.xml_exporter import timeline_rate, timeline_rate_notices
    odd = clip('variable.mov', 12.457627118644067, 11.8, audio=False)
    odd.selected_timestamp = TimestampCandidate('test', '', datetime(2026, 1, 1, tzinfo=timezone.utc), 1)
    odd.metadata['ffprobe.r_frame_rate'] = '100/1'
    rate, notice = timeline_rate(odd)
    assert float(rate[2]) == 12
    assert '12.457627' in notice
    assert not timeline_rate_notices([odd], [odd.path])
    phone = clip('phone.mov', 30.015175, 89.5547)
    phone.metadata['ffprobe.r_frame_rate'] = '30/1'
    assert float(timeline_rate(phone)[0][2]) == 30
    path = tmp_path / 'timeline.xml'
    write_timeline_xml(path, [odd, phone])
    root = ET.parse(path).getroot()
    assert int(root.findtext('./sequence/duration')) == round((11.8 + 89.5547) * 12)
    assert 'variable.mov' in root.findtext('./sequence/logginginfo/lognote')
    items = root.findall('./sequence/media/video/track/clipitem')
    assert items[0].findtext('end') == items[1].findtext('start')


@pytest.mark.parametrize('rate', [None, 0, float('nan'), float('inf'), -1, 300])
def test_invalid_rate_cannot_export(tmp_path, rate):
    with pytest.raises(ValueError):
        write_timeline_xml(tmp_path / 'timeline.xml', [clip('invalid.mov', rate)])
