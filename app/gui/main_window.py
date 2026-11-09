"""Folder selection and asynchronous metadata review window."""
import os

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDateTimeEdit,
                               QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QInputDialog,
                               QMessageBox, QPushButton, QProgressBar, QSplitter,
                               QTableWidget, QTableWidgetItem, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from app.core.xml_exporter import timeline_rate_notices, write_timeline_xml
from app.core.scanner import DEFAULT_EXTENSIONS
from app.core.session_report import read_session_report, write_session_report
from app.core.timestamp_corrector import apply_offset, override_timestamp, set_reference_time
from app.gui.camera_correction_dialog import CameraCorrectionDialog
from app.gui.export_review_dialog import ExportReviewDialog
from app.gui.scan_worker import ScanWorker


class MainWindow(QMainWindow):
    COLUMNS = ["Include", "Filename", "Camera / source", "Capture date / time (UTC)",
               "Duration", "Resolution", "Timestamp source", "Confidence", "Warnings"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Premiere Timeline Prep")
        self.resize(1180, 760)
        self.setMinimumSize(820, 540)
        self.worker = None
        self.videos = []
        self.tool_notices = []
        self.excluded_paths = set()
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title = QLabel("Premiere Timeline Prep")
        title.setObjectName("title")
        subtitle = QLabel("Prepare footage for an editable, chronological Premiere Pro timeline.")
        subtitle.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        folder_panel = QFrame()
        folder_panel.setObjectName("panel")
        folder_layout = QVBoxLayout(folder_panel)
        folder_layout.setContentsMargins(18, 16, 18, 16)
        heading = QLabel("1  Select video folders")
        heading.setObjectName("sectionTitle")
        folder_layout.addWidget(heading)
        folder_row = QHBoxLayout()
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_list.setMinimumHeight(76)
        self.folder_list.setMaximumHeight(118)
        folder_row.addWidget(self.folder_list, 1)
        folder_buttons = QVBoxLayout()
        self.add_folder_button = QPushButton("Add folder…")
        self.remove_folder_button = QPushButton("Remove selected")
        folder_buttons.addWidget(self.add_folder_button)
        folder_buttons.addWidget(self.remove_folder_button)
        folder_buttons.addStretch(1)
        folder_row.addLayout(folder_buttons)
        folder_layout.addLayout(folder_row)

        options_row = QHBoxLayout()
        self.recursive_check = QCheckBox("Include subfolders")
        self.recursive_check.setChecked(True)
        options_row.addWidget(self.recursive_check)
        options_row.addSpacing(18)
        options_row.addWidget(QLabel("Video formats:"))
        self.extension_list = QListWidget()
        self.extension_list.setFlow(QListWidget.LeftToRight)
        self.extension_list.setWrapping(True)
        self.extension_list.setMaximumHeight(68)
        self.extension_list.setMinimumWidth(500)
        self.extension_list.setSelectionMode(QAbstractItemView.NoSelection)
        for extension in sorted(DEFAULT_EXTENSIONS):
            item = QListWidgetItem(extension)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.extension_list.addItem(item)
        options_row.addWidget(self.extension_list, 1)
        folder_layout.addLayout(options_row)
        root.addWidget(folder_panel)

        review_row = QHBoxLayout()
        review_heading = QLabel("2  Review scanned footage")
        review_heading.setObjectName("sectionTitle")
        review_row.addWidget(review_heading)
        review_row.addStretch(1)
        review_row.addWidget(QLabel("Camera:"))
        self.camera_filter = QComboBox()
        self.camera_filter.addItem("All sources")
        self.camera_filter.setMinimumWidth(150)
        review_row.addWidget(self.camera_filter)
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search filenames or camera sources")
        self.search_field.setMaximumWidth(320)
        review_row.addWidget(self.search_field)
        root.addLayout(review_row)

        self.setup_notice = QLabel()
        self.setup_notice.setWordWrap(True)
        self.setup_notice.setStyleSheet("QLabel { background: #fff4d6; color: #704c00; padding: 9px 12px; border-radius: 5px; }")
        self.setup_notice.hide()
        root.addWidget(self.setup_notice)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        for column in range(4, len(self.COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.details_heading = QLabel("Select a clip to inspect its timestamp candidates and warnings.")
        self.details_heading.setObjectName("sectionTitle")
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Full file metadata and timestamp warnings will appear here.")
        self.details.setMinimumHeight(120)
        self.edit_timestamp_button = QPushButton("Edit selected timestamp…")
        self.edit_timestamp_button.setEnabled(False)
        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(0, 6, 0, 0)
        detail_header = QHBoxLayout()
        detail_header.addWidget(self.details_heading, 1)
        self.assign_source_button = QPushButton("Group selected clips…")
        self.assign_source_button.setEnabled(False)
        detail_header.addWidget(self.assign_source_button)
        self.correct_camera_button = QPushButton("Correct camera group…")
        self.correct_camera_button.setEnabled(False)
        detail_header.addWidget(self.correct_camera_button)
        detail_header.addWidget(self.edit_timestamp_button)
        details_layout.addLayout(detail_header)
        details_layout.addWidget(self.details)
        review_splitter = QSplitter(Qt.Vertical)
        review_splitter.addWidget(self.table)
        review_splitter.addWidget(details_panel)
        review_splitter.setSizes([420, 190])
        root.addWidget(review_splitter, 1)

        export_row = QHBoxLayout()
        export_hint = QLabel("3  Check the order, then export your timeline")
        export_hint.setObjectName("sectionTitle")
        export_row.addWidget(export_hint, 1)
        root.addLayout(export_row)
        footer = QHBoxLayout()
        self.status_label = QLabel("Add folders to begin.")
        self.status_label.setObjectName("status")
        footer.addWidget(self.status_label, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(190)
        self.progress.setTextVisible(False)
        self.progress.hide()
        footer.addWidget(self.progress)
        self.review_order_button = QPushButton("Review export order…")
        self.review_order_button.setEnabled(False)
        export_row.addWidget(self.review_order_button)
        self.export_xml_button = QPushButton("Export XML…")
        self.export_xml_button.setEnabled(False)
        self.export_xml_button.setToolTip("Experimental chronological timeline for Premiere; import validation required")
        export_row.addWidget(self.export_xml_button)
        self.open_session_button = QPushButton("Open session…")
        footer.addWidget(self.open_session_button)
        self.export_report_button = QPushButton("Export report…")
        self.export_report_button.setEnabled(False)
        footer.addWidget(self.export_report_button)
        self.scan_button = QPushButton("Scan folders")
        self.scan_button.setObjectName("primaryButton")
        self.scan_button.setMinimumWidth(140)
        footer.addWidget(self.scan_button)
        root.addLayout(footer)

        self.setCentralWidget(central)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f5f7fa; color: #1e293b; font-size: 13px; }
            QLabel#title { font-size: 27px; font-weight: 700; color: #14243a; }
            QLabel#subtitle { color: #64748b; font-size: 14px; }
            QLabel#sectionTitle { font-size: 15px; font-weight: 650; color: #23364d; }
            QFrame#panel { background: white; border: 1px solid #dce3eb; border-radius: 10px; }
            QListWidget, QTableWidget, QLineEdit { background: white; border: 1px solid #d7dee8; border-radius: 5px; }
            QListWidget { padding: 4px; }
            QTableWidget { gridline-color: #e8edf2; selection-background-color: #dcecff; selection-color: #14243a; }
            QHeaderView::section { background: #edf2f7; color: #475569; padding: 8px 6px; border: 0; border-right: 1px solid #dce3eb; font-weight: 600; }
            QPushButton { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 12px; }
            QPushButton:hover { background: #f1f5f9; }
            QPushButton#primaryButton { background: #1769aa; color: white; border: none; font-weight: 650; padding: 10px 16px; }
            QPushButton#primaryButton:hover { background: #13598f; }
            QLineEdit { padding: 8px 10px; }
            QProgressBar { border: 0; background: #e2e8f0; border-radius: 4px; height: 8px; }
            QProgressBar::chunk { background: #2e8bca; border-radius: 4px; }
            QLabel#status { color: #64748b; }
        """)

        self.add_folder_button.clicked.connect(self._add_folder)
        self.remove_folder_button.clicked.connect(self._remove_folders)
        self.scan_button.clicked.connect(self._start_scan)
        self.review_order_button.clicked.connect(self._review_export_order)
        self.export_xml_button.clicked.connect(self._export_xml)
        self.open_session_button.clicked.connect(self._open_session)
        self.export_report_button.clicked.connect(self._export_report)
        self.table.itemChanged.connect(self._include_changed)
        self.search_field.textChanged.connect(self._filter_rows)
        self.camera_filter.currentTextChanged.connect(self._filter_rows)
        self.table.currentCellChanged.connect(self._show_row_details)
        self.edit_timestamp_button.clicked.connect(self._edit_selected_timestamp)
        self.assign_source_button.clicked.connect(self._assign_camera_source)
        self.correct_camera_button.clicked.connect(self._correct_camera_group)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a video folder")
        if not folder:
            return
        folder = os.path.abspath(folder)
        existing = {os.path.normcase(os.path.realpath(self.folder_list.item(i).text()))
                    for i in range(self.folder_list.count())}
        if os.path.normcase(os.path.realpath(folder)) not in existing:
            self.folder_list.addItem(folder)

    def _remove_folders(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))

    def _start_scan(self):
        folders = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        if not folders:
            QMessageBox.information(self, "Select folders", "Add at least one folder before scanning.")
            return
        extensions = [self.extension_list.item(i).text() for i in range(self.extension_list.count())
                      if self.extension_list.item(i).checkState() == Qt.Checked]
        if not extensions:
            QMessageBox.information(self, "Select formats", "Choose at least one supported video format.")
            return
        self.open_session_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.export_report_button.setEnabled(False)
        self.export_xml_button.setEnabled(False)
        self.review_order_button.setEnabled(False)
        self.add_folder_button.setEnabled(False)
        self.remove_folder_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status_label.setText("Starting scan…")
        self.worker = ScanWorker(folders, extensions, self.recursive_check.isChecked())
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress.connect(self._update_progress)
        self.worker.completed.connect(self._scan_completed)
        self.worker.start()

    def _update_progress(self, current, total):
        self.progress.setRange(0, total)
        self.progress.setValue(current)
        self.status_label.setText("Analyzed {} of {} videos".format(current, total))

    def _scan_completed(self, videos):
        self.videos = videos
        self.excluded_paths.intersection_update(video.path for video in videos)
        self.export_report_button.setEnabled(bool(videos))
        self.export_xml_button.setEnabled(bool(videos))
        self.review_order_button.setEnabled(bool(videos))
        self.tool_notices = self._collect_tool_notices(videos)
        current_camera = self.camera_filter.currentText()
        self.camera_filter.blockSignals(True)
        self.camera_filter.clear()
        self.camera_filter.addItem("All sources")
        for camera in sorted({video.camera or "Unknown" for video in videos}, key=str.casefold):
            self.camera_filter.addItem(camera)
        index = self.camera_filter.findText(current_camera)
        self.camera_filter.setCurrentIndex(index if index >= 0 else 0)
        self.camera_filter.blockSignals(False)
        if self.tool_notices:
            self.setup_notice.setText("Metadata tools unavailable: " + " ".join(self.tool_notices))
            self.setup_notice.show()
        else:
            self.setup_notice.hide()
        self._populate_table(videos)
        self.progress.hide()
        self.open_session_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        self.add_folder_button.setEnabled(True)
        self.remove_folder_button.setEnabled(True)
        errors = sum(1 for video in videos if video.error)
        self.status_label.setText("{} video{} found · {} clip{} with timestamp warnings{}".format(
            len(videos), "s" if len(videos) != 1 else "",
            sum(bool(self._review_warnings(v)) for v in videos),
            "s" if sum(bool(self._review_warnings(v)) for v in videos) != 1 else "",
            " · {} could not be analyzed".format(errors) if errors else ""))
        if not videos:
            self.status_label.setText("No matching video files found.")

    def _populate_table(self, videos):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(videos))
        for row, video in enumerate(videos):
            include = QTableWidgetItem()
            include.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            include.setData(Qt.UserRole, video.path)
            include.setCheckState(Qt.Unchecked if video.path in self.excluded_paths else Qt.Checked)
            self.table.setItem(row, 0, include)
            timestamp = video.selected_timestamp
            capture = timestamp.normalized.isoformat(timespec="seconds").replace("+00:00", "Z") if timestamp and timestamp.normalized else "Unknown"
            duration = self._duration(video.duration_seconds)
            resolution = "{} × {}".format(video.width, video.height) if video.width and video.height else "—"
            values = [video.filename, video.camera or "Unknown", capture, duration, resolution,
                      timestamp.source if timestamp else "—",
                      "{:.0f}%".format(timestamp.confidence * 100) if timestamp else "—",
                      "⚠ {}".format(len(self._review_warnings(video))) if self._review_warnings(video) else "OK"]
            for column, value in enumerate(values, 1):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, video.path)
                if column == 1:
                    item.setToolTip(video.path)
                if column == 8:
                    item.setToolTip("\n".join(self._review_warnings(video)) or "No timestamp warnings")
                    if self._review_warnings(video):
                        item.setForeground(QColor("#a45400"))
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self.table.sortItems(3, Qt.AscendingOrder)
        self._filter_rows(self.search_field.text())
        if videos:
            self.table.setCurrentCell(0, 1)
        else:
            self.details.clear()
            self.details_heading.setText("Select a clip to inspect its timestamp candidates and warnings.")
            self.edit_timestamp_button.setEnabled(False)
            self.assign_source_button.setEnabled(False)
            self.correct_camera_button.setEnabled(False)

    def _include_changed(self, item):
        if item.column() != 0:
            return
        path = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self.excluded_paths.discard(path)
        else:
            self.excluded_paths.add(path)

    def _open_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open session", "", "JSON session report (*.json)")
        if not path:
            return
        try:
            videos, excluded, folders = read_session_report(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Session could not be opened", str(exc))
            return
        self.excluded_paths = excluded
        self.folder_list.clear()
        self.folder_list.addItems(folders)
        self._scan_completed(videos)
        missing = sum(not os.path.isfile(video.path) for video in videos)
        self.status_label.setText("Opened {} clips from session{}".format(
            len(videos), " · {} media files unavailable at saved paths".format(missing) if missing else ""))

    def _review_export_order(self):
        ExportReviewDialog(self.videos, self.excluded_paths, parent=self).exec()

    def _export_xml(self):
        try:
            notices = timeline_rate_notices(self.videos, self.excluded_paths)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "XML could not be exported", str(exc))
            return
        dialog = ExportReviewDialog(self.videos, self.excluded_paths, notices,
                                    exporting=True, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export experimental Premiere timeline", "timeline.xml", "Final Cut Pro 7 XML (*.xml)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".xml"
        try:
            write_timeline_xml(path, self.videos, excluded_paths=self.excluded_paths)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "XML could not be exported", str(exc))
            return
        self.status_label.setText("Saved experimental XML. Import in Premiere to verify picture, sound, timing, and media links.")

    def _export_report(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export session report", "session-report.json",
            "JSON audit report (*.json);;CSV clip inventory (*.csv)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".csv" if selected_filter.startswith("CSV") else ".json"
        try:
            write_session_report(
                path, self.videos, excluded_paths=self.excluded_paths,
                folders=[self.folder_list.item(i).text() for i in range(self.folder_list.count())])
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Report could not be saved", str(exc))
            return
        self.status_label.setText("Saved session report to {}".format(path))

    @staticmethod
    def _collect_tool_notices(videos):
        notices = []
        for video in videos:
            for warning in video.warnings:
                if warning.startswith("FFprobe was not found") or warning.startswith("ExifTool was not found"):
                    if warning not in notices:
                        notices.append(warning)
        return notices

    @staticmethod
    def _review_warnings(video):
        setup_prefixes = ("FFprobe was not found", "ExifTool was not found")
        return [warning for warning in video.warnings if not warning.startswith(setup_prefixes)]

    def _selected_video(self):
        row = self.table.currentRow()
        item = self.table.item(row, 1) if row >= 0 else None
        path = item.data(Qt.UserRole) if item else None
        return next((video for video in self.videos if video.path == path), None)

    def _show_row_details(self, row, _column, _previous_row, _previous_column):
        video = self._selected_video()
        if video is None:
            self.details.clear()
            self.details_heading.setText("Select a clip to inspect its timestamp candidates and warnings.")
            self.edit_timestamp_button.setEnabled(False)
            self.assign_source_button.setEnabled(bool(self.table.selectionModel().selectedRows()))
            self.correct_camera_button.setEnabled(False)
            return
        self.details_heading.setText("Clip review: {}".format(video.filename))
        self.edit_timestamp_button.setEnabled(video.selected_timestamp is not None)
        self.assign_source_button.setEnabled(True)
        self.correct_camera_button.setEnabled(bool(video.camera))
        timestamp = video.selected_timestamp
        lines = ["File: {}".format(video.path),
                 "Size: {} bytes    Duration: {}    Resolution: {}    Frame rate: {}".format(
                     video.size_bytes, self._duration(video.duration_seconds),
                     "{} × {}".format(video.width, video.height) if video.width and video.height else "unknown",
                     "{:.3f} fps".format(video.frame_rate) if video.frame_rate else "unknown"),
                 "Camera/source: {}    Video codec: {}    Audio codec: {}".format(
                     video.camera or "Unknown", video.video_codec or "unknown", video.audio_codec or "none"), ""]
        if timestamp:
            lines.extend(["SELECTED TIMESTAMP", "  Source: {}    Confidence: {:.0f}%".format(timestamp.source, timestamp.confidence * 100),
                          "  Raw: {}".format(timestamp.raw_value),
                          "  Normalized UTC: {}".format(timestamp.normalized.isoformat() if timestamp.normalized else "unparsed")])
        else:
            lines.extend(["SELECTED TIMESTAMP", "  No usable timestamp was selected."])
        lines.extend(["", "ALL TIMESTAMP CANDIDATES"])
        if video.timestamp_candidates:
            for candidate in video.timestamp_candidates:
                normalized = candidate.normalized.isoformat() if candidate.normalized else "unparsed"
                lines.append("  • {} ({}% confidence)".format(candidate.source, round(candidate.confidence * 100)))
                lines.append("    Raw: {}".format(candidate.raw_value))
                lines.append("    Normalized UTC: {}".format(normalized))
                lines.extend("    Candidate note: {}".format(note) for note in candidate.warnings)
        else:
            lines.append("  No timestamp metadata candidates were found.")
        warnings = self._review_warnings(video)
        lines.extend(["", "WARNINGS TO REVIEW"])
        lines.extend("  • {}".format(warning) for warning in warnings)
        if not warnings:
            lines.append("  None")
        if self.tool_notices:
            lines.extend(["", "SETUP NOTICES"])
            lines.extend("  • {}".format(notice) for notice in self.tool_notices)
        self.details.setPlainText("\n".join(lines))

    def _edit_selected_timestamp(self):
        video = self._selected_video()
        if not video or not video.selected_timestamp or not video.selected_timestamp.normalized:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit capture date and time")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Set the actual capture time for this clip (UTC)."))
        editor = QDateTimeEdit(QDateTime.fromString(
            video.selected_timestamp.normalized.strftime("%Y-%m-%dT%H:%M:%SZ"), Qt.ISODate), dialog)
        editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss 'UTC'")
        editor.setCalendarPopup(True)
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            override_timestamp(video, editor.dateTime().toPython())
            self._populate_table(self.videos)
            self.status_label.setText("Updated capture time for {}.".format(video.filename))

    def _assign_camera_source(self):
        selected_rows = self.table.selectionModel().selectedRows()
        videos = []
        for model_index in selected_rows:
            filename_item = self.table.item(model_index.row(), 1)
            path = filename_item.data(Qt.UserRole) if filename_item else None
            video = next((entry for entry in self.videos if entry.path == path), None)
            if video:
                videos.append(video)
        if not videos:
            video = self._selected_video()
            if video:
                videos = [video]
        if not videos:
            return
        initial = videos[0].camera or "Camera 1"
        name, accepted = QInputDialog.getText(self, "Assign camera/source", "Source name for selected clips:", text=initial)
        if not accepted or not name.strip():
            return
        name = name.strip()
        for video in videos:
            video.camera = name
        self._refresh_camera_filter()
        self._populate_table(self.videos)
        self.status_label.setText("Assigned {} clip{} to {}.".format(len(videos), "s" if len(videos) != 1 else "", name))

    def _correct_camera_group(self):
        reference = self._selected_video()
        if not reference or not reference.camera:
            QMessageBox.information(self, "Choose a camera", "Select a clip with an assigned camera/source first.")
            return
        dialog = CameraCorrectionDialog(reference.camera,
                                        reference.selected_timestamp.normalized if reference.selected_timestamp else None,
                                        self)
        if dialog.exec() != QDialog.Accepted:
            return
        group = [video for video in self.videos if video.camera == reference.camera]
        if dialog.reference_mode.isChecked():
            if not reference.selected_timestamp:
                QMessageBox.warning(self, "No reference timestamp", "The selected clip has no timestamp to correct.")
                return
            offset = set_reference_time(group, reference, dialog.actual_reference_time())
        else:
            from datetime import timedelta
            offset = timedelta(seconds=dialog.offset_seconds())
            for video in group:
                apply_offset(video, offset)
        self._populate_table(self.videos)
        self.status_label.setText("Applied {} seconds to {} clip{} in {}.".format(
            int(offset.total_seconds()), len(group), "s" if len(group) != 1 else "", reference.camera))

    def _refresh_camera_filter(self):
        current = self.camera_filter.currentText()
        self.camera_filter.blockSignals(True)
        self.camera_filter.clear()
        self.camera_filter.addItem("All sources")
        for camera in sorted({video.camera or "Unknown" for video in self.videos}, key=str.casefold):
            self.camera_filter.addItem(camera)
        self.camera_filter.setCurrentIndex(max(0, self.camera_filter.findText(current)))
        self.camera_filter.blockSignals(False)
        self._filter_rows()

    @staticmethod
    def _duration(seconds):
        if seconds is None:
            return "—"
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        return "{:02}:{:02}:{:02}".format(hours, minutes, seconds)

    def _filter_rows(self, _query=None):
        query = self.search_field.text().casefold().strip()
        camera = self.camera_filter.currentText()
        for row in range(self.table.rowCount()):
            matches_search = not query or any(query in (self.table.item(row, column).text().casefold()
                                                         if self.table.item(row, column) else "")
                                              for column in (1, 2))
            matches_camera = camera == "All sources" or (self.table.item(row, 2) and self.table.item(row, 2).text() == camera)
            matches = matches_search and matches_camera
            self.table.setRowHidden(row, not matches)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(3000)
        super().closeEvent(event)
