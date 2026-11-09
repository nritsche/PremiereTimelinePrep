"""Regression checks for exact export order and bounded timing notices."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QDialogButtonBox

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
