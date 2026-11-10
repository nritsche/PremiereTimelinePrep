"""Regression checks for exact export order and bounded timing notices."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from app.gui.bounded_dialog import WarningDialog

from app.core.chronological_sorter import chronological_sort
from app.gui.export_review_dialog import ExportReviewDialog
from app.models.video_file import VideoFile, TimestampCandidate
from datetime import datetime, timezone


@pytest.fixture(scope='module')
def application():
    return QApplication.instance() or QApplication([])


def test_preview_uses_export_order_and_exclusions(application):
    known = VideoFile('/known.mov', 'known.mov', 1, selected_timestamp=TimestampCandidate(
        'test', '', datetime(2026, 1, 1, tzinfo=timezone.utc), 1))
    unknown = VideoFile('/unknown.mov', 'unknown.mov', 1)
    excluded = VideoFile('/excluded.mov', 'excluded.mov', 1)
    dialog = ExportReviewDialog([unknown, excluded, known], [excluded.path])
    expected = chronological_sort([unknown, known])
    assert [dialog.table.item(row, 1).text() for row in range(dialog.table.rowCount())] == [v.filename for v in expected]
    assert dialog.table.item(1, 2).text() == 'Unknown'
    dialog.close()


def test_long_notices_scroll_with_buttons_inside_window(application):
    dialog = ExportReviewDialog([], notices=['a long filename ' * 100] * 200, exporting=True)
    dialog.resize(600, 480)
    dialog.show()
    application.processEvents()
    assert dialog.height() <= dialog.screen().availableGeometry().height()
    assert dialog.buttons.geometry().bottom() < dialog.height()
    assert dialog.timing_details.verticalScrollBar().maximum() > 0
    assert dialog.buttons.button(QDialogButtonBox.Cancel).isDefault()
    dialog.close()


@pytest.mark.parametrize('font_size', [14, 26])
def test_entire_save_review_scrolls_but_footer_remains_clickable(application, font_size):
    dialog = ExportReviewDialog([], notices=['clip-' + 'x' * 5000] * 200, exporting=True)
    dialog.setFont(QFont('Sans Serif', font_size))
    dialog.resize(560, 350)
    dialog.show()
    application.processEvents()
    assert dialog.body_scroll.verticalScrollBar().maximum() > 0
    scrollbar = dialog.body_scroll.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    application.processEvents()
    assert scrollbar.value() > 0
    cancel = dialog.buttons.button(QDialogButtonBox.Cancel)
    assert dialog.buttons.geometry().bottom() < dialog.height()
    assert dialog.body_scroll.geometry().bottom() < dialog.buttons.geometry().top()
    assert dialog.height() <= dialog.screen().availableGeometry().height()
    QTest.mouseClick(cancel, Qt.LeftButton)
    assert not dialog.isVisible()
    assert dialog.result() == QDialog.Rejected


def test_long_save_error_scrolls_and_ok_is_always_available(application):
    dialog = WarningDialog('Project could not be saved', ('A very long file path ' * 200 + '\n') * 200)
    dialog.setFont(QFont('Sans Serif', 24))
    dialog.resize(500, 300)
    dialog.show()
    application.processEvents()
    scrollbar = dialog.message.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    assert scrollbar.value() > 0
    assert dialog.buttons.geometry().bottom() < dialog.height()
    QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.Ok), Qt.LeftButton)
    assert dialog.result() == QDialog.Accepted
