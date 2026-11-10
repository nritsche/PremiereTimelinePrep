from app.core.source_grouping import assign_automatic_sources, camera_identity
from app.models.video_file import VideoFile


def test_grouped_exif_camera_fields_and_serials_are_used():
    assert camera_identity({'IFD0:Make': 'Sony', 'IFD0:Model': 'Sony A7',
                            'ExifIFD:BodySerialNumber': 'camera-42'}, {}) == 'Sony A7 · camera-42'
    assert camera_identity({}, {'com.apple.quicktime.make': 'Apple',
                                'com.apple.quicktime.model': 'iPhone'}) == 'Apple iPhone'


def test_folder_sources_skip_card_directories_and_do_not_overwrite_manual_groups(tmp_path):
    first = VideoFile(str(tmp_path / 'Camera A/DCIM/100MEDIA/001.mov'), '001.mov', 1)
    second = VideoFile(str(tmp_path / 'Camera B/PRIVATE/AVCHD/BDMV/STREAM/001.mts'), '001.mts', 1)
    manual = VideoFile(str(tmp_path / 'Camera A/002.mov'), '002.mov', 1, camera='Custom source')
    assign_automatic_sources([first, second, manual])
    assert first.camera == 'Folder: Camera A'
    assert second.camera == 'Folder: Camera B'
    assert manual.camera == 'Custom source'
    assert 'identity unavailable' in first.metadata['source_group_basis']


def test_duplicate_folder_names_stay_separate_and_saved_camera_metadata_is_recovered(tmp_path):
    videos = [VideoFile(str(tmp_path / prefix / 'footage/clip.mov'), 'clip.mov', 1)
              for prefix in ('day1', 'day2')]
    saved = VideoFile(str(tmp_path / 'saved.mov'), 'saved.mov', 1,
                      metadata={'exiftool.raw': {'IFD0:Model': 'Camera model'}})
    assign_automatic_sources(videos + [saved])
    assert videos[0].camera != videos[1].camera
    assert saved.camera == 'Camera model'
