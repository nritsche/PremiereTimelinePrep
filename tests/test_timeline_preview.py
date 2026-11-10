import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QApplication

from app.gui.timeline_preview import TimelinePreview
from app.gui.thumbnail_service import ThumbnailService
from app.models.video_file import TimestampCandidate, VideoFile
from app.core.xml_exporter import write_timeline_xml


@pytest.fixture
def preview():
    application = QApplication.instance() or QApplication([])
    widget = TimelinePreview()
    yield widget
    widget.stop()
    widget.close()
    application.processEvents()


def clip(tmp_path, name, seconds=1, dated=True):
    return VideoFile(str(tmp_path / name), name, 1, duration_seconds=seconds,
        width=160, height=120, frame_rate=24000/1001, camera='Camera A',
        selected_timestamp=TimestampCandidate('test', '', datetime(2026, 1, 1, tzinfo=timezone.utc), 1) if dated else None,
        metadata={'ffprobe.streams': [{'codec_type': 'video'}]})


def test_visual_sequence_matches_xml_boundaries_order_and_exclusions(preview, tmp_path):
    videos = [clip(tmp_path, 'unknown.mov', 2, False), clip(tmp_path, 'b.mov', 1.11),
              clip(tmp_path, 'a.mov', 1.23), clip(tmp_path, 'excluded.mov')]
    preview.set_clips(videos, [videos[-1].path])
    path = tmp_path / 'timeline.xml'
    write_timeline_xml(path, videos, excluded_paths=[videos[-1].path])
    items = ET.parse(path).findall('./sequence/media/video/track/clipitem')
    assert [v.filename for v in preview.clips] == [item.findtext('name') for item in items]
    assert [(round(start * (24000/1001)), round(end * (24000/1001))) for start, end in preview.spans] == [
        (int(item.findtext('start')), int(item.findtext('end'))) for item in items]
    preview.mode.setCurrentIndex(1)
    assert preview.cards.count() == 4
    assert 'Excluded' in preview.items[videos[-1].path].text()
    # Browsing a source does not change the assembly or bring excluded clips back.
    assert len(preview.clips) == 3


def test_scrubbing_crosses_clip_boundary_and_filter_does_not_change_sequence(preview, tmp_path):
    videos = [clip(tmp_path, 'a.mov'), clip(tmp_path, 'b.mov')]
    videos[1].camera = 'Camera B'
    preview.set_clips(videos)
    preview.sources.setCurrentText('Camera A')
    preview.scrub.setValue(75000)
    preview._seek()
    assert preview.current_path == videos[1].path
    assert preview.cards.count() == 1
    assert len(preview.clips) == 2


def test_missing_media_is_explicit_and_exclusion_can_be_restored(preview, tmp_path):
    preview.service.executable = None
    video = clip(tmp_path, 'missing.mov')
    preview.set_clips([video], [video.path])
    assert preview.cards.count() == 0
    preview.mode.setCurrentIndex(1)
    assert 'unavailable' in preview.image.text().lower()
    choices = []
    preview.inclusionChanged.connect(lambda path, checked: choices.append((path, checked)))
    preview.include.setChecked(True)
    assert choices == [(video.path, True)]


def test_asynchronous_frame_decode_and_cache_invalidation(preview, tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg unavailable; packaged Windows self-test requires decoding')
    media = tmp_path / 'café preview.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                    '-i', 'color=c=blue:s=160x120:r=25', '-t', '0.3', '-c:v', 'mpeg4', str(media)],
                   check=True, timeout=30)
    service = ThumbnailService(executable=ffmpeg)
    images = []
    loop = QEventLoop()
    service.ready.connect(lambda token, image, error: (images.append((image, error)), loop.quit()))
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(20000)
    video = clip(tmp_path, media.name)
    service.request(video, 0, 'frame')
    loop.exec()
    timer.stop()
    assert images and not images[0][0].isNull() and not images[0][1]
    assert len(service.cache) == 1
    first_key = next(iter(service.cache))
    stat = media.stat()
    os.utime(media, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    service.request(video, 0, 'changed')
    assert first_key not in service.waiters
    assert len(service.queue) == 1
    service.stop()
    assert not service.queue
