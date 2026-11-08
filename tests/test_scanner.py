from app.core.scanner import discover_videos


def test_scan_extensions_and_overlapping_roots(tmp_path):
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    video = sub / "one.MP4"
    video.write_bytes(b"video")
    (sub / "ignore.txt").write_text("x")
    found = list(discover_videos([str(root), str(sub)]))
    assert found == [str(video)]
