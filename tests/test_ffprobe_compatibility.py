from scripts.check_ffprobe_compatibility import differences


def test_metadata_comparison_detects_timestamp_rotation_audio_and_timing_loss():
    expected = {'streams': [{'width': 1920, 'channels': 2, 'time_base': '1/30000',
                             'tags': {'creation_time': '2026-01-02T03:04:05Z'},
                             'side_data_list': [{'rotation': 90}]}]}
    actual = {'streams': [{'width': 1920, 'channels': 1, 'time_base': '1/30',
                           'tags': {}, 'side_data_list': []}]}
    assert set(differences(expected, actual)) == {
        '/streams/0/channels', '/streams/0/time_base',
        '/streams/0/tags/creation_time', '/streams/0/side_data_list/length'}


def test_small_build_description_omission_is_allowed_but_codec_loss_is_not():
    assert differences({'codec_name': 'h264', 'codec_long_name': 'H.264'},
                       {'codec_name': 'h264'}) == []
    assert differences({'codec_name': 'h264'}, {}) == ['/codec_name']
