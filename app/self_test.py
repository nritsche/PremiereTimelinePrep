"""Exercise packaged imports and bundled tools using synthetic media in CI."""
import json
from pathlib import Path
import subprocess
import traceback


def run_self_test(result_path, media_path):
    result = {"success": False}
    try:
        from PySide6.QtWidgets import QApplication
        from app.core.metadata_extractor import _bundled_tool, extract_video
        from app.core.xml_exporter import write_timeline_xml
        from app.gui.main_window import MainWindow
        from app.core.session_report import write_session_report, read_session_report
        import tempfile
        ffprobe, exiftool = _bundled_tool('ffprobe'), _bundled_tool('exiftool')
        if not ffprobe or not exiftool:
            raise RuntimeError('Packaged media tools not found')
        result['bundled_tools'] = {'ffprobe': Path(ffprobe).name, 'exiftool': Path(exiftool).name}
        for name, tool, flag in [('ffprobe', ffprobe, '-version'), ('exiftool', exiftool, '-ver')]:
            result[name + '_version'] = subprocess.check_output([tool, flag], timeout=30, text=True,
                encoding='utf-8', errors='replace').splitlines()[0]
        video = extract_video(str(Path(media_path).resolve()))
        if not video.width or not video.duration_seconds or not video.audio_codec:
            raise RuntimeError('Synthetic video/audio metadata missing')
        tool_errors = [w for w in video.warnings if w.startswith(('FFprobe:', 'ExifTool:'))]
        if tool_errors:
            raise RuntimeError('; '.join(tool_errors))
        application = QApplication.instance() or QApplication([])
        window = MainWindow()
        window._scan_completed([video])
        if window.table.rowCount() != 1:
            raise RuntimeError('GUI did not display synthetic clip')
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'session.json'
            write_session_report(report, [video])
            loaded, _, _ = read_session_report(report)
            write_timeline_xml(Path(directory) / 'timeline.xml', loaded)
        window._set_dirty(False)
        window.close()
        application.processEvents()
        result['success'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    Path(result_path).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['success'] else 1
