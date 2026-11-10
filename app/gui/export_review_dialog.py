"""Bounded, scrollable review of the exact XML assembly order."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox,
                               QHeaderView, QLabel, QPlainTextEdit, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QTabWidget)

from app.core.chronological_sorter import chronological_sort
from app.gui.timeline_preview import TimelinePreview


class ExportReviewDialog(QDialog):
    def __init__(self, videos, excluded_paths=(), notices=(), *, exporting=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review XML export" if exporting else "Review export order")
        screen = self.screen().availableGeometry()
        self.setMaximumSize(max(1, screen.width() - 40), max(1, screen.height() - 60))
        self.resize(min(1120, self.maximumWidth()), min(780, self.maximumHeight()))
        layout = QVBoxLayout(self)
        excluded = set(excluded_paths)
        clips = chronological_sort([video for video in videos if video.path not in excluded])
        explanation = QLabel(
            "{} included clips, in the exact order used by XML export. Clips play back-to-back; "
            "recording gaps are removed. Scrub to inspect still frames; check sound/playback in Premiere. "
            "Close this window to change dates, sources or inclusion.".format(len(clips)))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.table = QTableWidget(len(clips), 5)
        self.table.setHorizontalHeaderLabels(["Order", "Clip", "Recording time (UTC)", "Camera / source", "Review"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(2, 195)
        self.table.setColumnWidth(4, 210)
        for row, video in enumerate(clips):
            stamp = video.selected_timestamp
            instant = stamp.normalized if stamp else None
            flags = []
            if not instant:
                flags.append("No recording date — placed last")
            if stamp and stamp.confidence < .7:
                flags.append("Date needs review")
            if video.warnings:
                flags.append("{} warning(s)".format(len(video.warnings)))
            values = [str(row + 1), video.filename,
                      instant.isoformat(timespec="seconds") if instant else "Unknown",
                      video.camera or "Unknown", "; ".join(flags) or "—"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(video.path if column == 1 else value)
                self.table.setItem(row, column, item)
        tabs = QTabWidget()
        self.preview = TimelinePreview(self)
        self.preview.include.hide()
        self.preview.edit_actions.hide()
        self.preview.summary.hide()
        self.preview.hint.hide()
        self.preview.set_clips(videos, excluded_paths)
        tabs.addTab(self.preview, 'Visual timeline')
        tabs.addTab(self.table, 'Recording dates & warnings')
        layout.addWidget(tabs, 1)
        self.finished.connect(lambda _: self.preview.stop())
        if notices:
            summary = QLabel(
                "Timing notice: {} clip(s) have an uneven or unusual frame rate. XML needs a fixed rate, "
                "so the app uses an approximate rate and keeps the overall recorded duration. "
                "This does not change clip order or convert your video files. After importing, check "
                "playback and sound sync, especially near the end of these clips.".format(len(notices)))
            summary.setWordWrap(True)
            layout.addWidget(summary)
            self.timing_details = QPlainTextEdit()
            self.timing_details.setReadOnly(True)
            self.timing_details.setPlainText("\n\n".join(notices))
            self.timing_details.setMaximumHeight(120)
            self.timing_details.setMinimumHeight(45)
            layout.addWidget(self.timing_details)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel if exporting else QDialogButtonBox.Close)
        if exporting:
            export = self.buttons.addButton("Export XML…", QDialogButtonBox.AcceptRole)
            export.setDefault(False)
            self.buttons.button(QDialogButtonBox.Cancel).setDefault(True)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
