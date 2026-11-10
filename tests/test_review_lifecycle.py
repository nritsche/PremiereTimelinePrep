import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from app.gui.main_window import MainWindow
from app.models.video_file import VideoFile


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    instance = MainWindow()
    yield instance
    instance.worker = None
    instance._set_dirty(False)
    instance.close()


def test_busy_worker_keeps_window_alive_until_finished(window):
    class BusyWorker:
        interrupted = False
        def isRunning(self): return True
        def requestInterruption(self): self.interrupted = True
    worker = BusyWorker()
    window.worker = worker
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert worker.interrupted
    assert window._close_pending


def test_unsaved_close_cancel_preserves_review(window, monkeypatch):
    window._set_dirty()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Cancel)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert window.dirty


def test_undated_clip_can_be_edited_and_inclusion_marks_dirty(window):
    window._scan_completed([VideoFile('/missing.mov', 'missing.mov', 1)])
    assert window.edit_timestamp_button.isEnabled()
    window._set_dirty(False)
    from PySide6.QtCore import Qt
    window.table.item(0, 0).setCheckState(Qt.Unchecked)
    assert window.dirty
    assert '/missing.mov' in window.excluded_paths


def test_cancelled_save_prevents_discard(window, monkeypatch):
    window._set_dirty()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Save)
    monkeypatch.setattr(window, '_save_session', lambda: False)
    assert not window._confirm_discard()


def test_project_button_saves_reloadable_review_and_scan_is_with_folders(window, monkeypatch, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFileDialog
    from app.core.session_report import read_session_report
    video = VideoFile(str(tmp_path / 'missing.mov'), 'missing.mov', 1)
    window._scan_completed([video])
    window.excluded_paths.add(video.path)
    target = tmp_path / 'project.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    window.export_report_button.click()
    loaded, excluded, _ = read_session_report(target)
    assert loaded[0].camera == video.camera
    assert excluded == {video.path}
    assert not window.dirty
    assert window.folder_panel.isAncestorOf(window.scan_button)
