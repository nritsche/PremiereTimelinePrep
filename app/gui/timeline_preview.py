"""Visual assembly review using the same clip order and frame boundaries as XML."""
from bisect import bisect_right
import hashlib

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QSlider, QSplitter, QVBoxLayout, QWidget, QSizePolicy, QScrollArea)

from app.core.chronological_sorter import chronological_sort
from app.core.xml_exporter import assembly_frame_spans, timeline_rate
from app.gui.thumbnail_service import ThumbnailService


def source_color(source):
    palette = ['#2563eb', '#9333ea', '#0d9488', '#d97706', '#db2777', '#4f46e5', '#52731b']
    return QColor(palette[int(hashlib.sha256((source or '').encode()).hexdigest()[:8], 16) % len(palette)])


def clock(seconds):
    milliseconds = max(0, round(seconds * 1000))
    total, ms = divmod(milliseconds, 1000)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f'{hours:02}:{minutes:02}:{secs:02}.{ms:03}'


class FrameLabel(QLabel):
    """Fit the image at paint time, including when a splitter changes its size."""
    def __init__(self, text):
        super().__init__(text)
        self.frame = QPixmap()

    def clear(self):
        self.frame = QPixmap()
        super().clear()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.frame.isNull():
            image = self.frame.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter = QPainter(self)
            painter.drawPixmap((self.width() - image.width()) // 2, (self.height() - image.height()) // 2, image)


class AssemblyStrip(QWidget):
    seek = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(58)
        self.clips, self.spans, self.position = [], [], 0
        self.setToolTip('Click the duration strip to inspect that part of the exported sequence')

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#e2e8f0'))
        if not self.spans:
            painter.drawText(self.rect(), Qt.AlignCenter, 'Timeline duration appears after scanning valid media')
            return
        total = self.spans[-1][1]
        for index, (clip, (start, end)) in enumerate(zip(self.clips, self.spans)):
            x, right = start / total * self.width(), end / total * self.width()
            painter.fillRect(QRectF(x, 2, max(.5, right - x), self.height() - 4), source_color(clip.camera))
            painter.setPen(QColor('white'))
            if right - x > 28:
                painter.drawText(QRectF(x + 3, 2, right - x - 6, self.height() - 4), Qt.AlignCenter, str(index + 1))
            painter.drawLine(round(x), 2, round(x), self.height() - 2)
        painter.setPen(QColor('#111827'))
        x = round(self.position / total * self.width())
        painter.drawLine(x, 0, x, self.height())

    def mousePressEvent(self, event):
        if self.spans:
            self.seek.emit(max(0., min(.999999, event.position().x() / max(1, self.width()))))


class TimelinePreview(QWidget):
    clipSelected = Signal(str)
    inclusionChanged = Signal(str, bool)
    editRequested = Signal()
    correctionRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.videos, self.clips, self.spans = [], [], []
        self.excluded = set()
        self.generation = 0
        self.current_path = None
        self.frame_token = 0
        self.items = {}
        self.requested = set()
        self.service = ThumbnailService(self)
        self.service.ready.connect(self._frame_ready)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        self.summary = QLabel('Scan footage to preview the assembled timeline.')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.strip = AssemblyStrip()
        layout.addWidget(self.strip)
        scrub_row = QHBoxLayout()
        self.previous = QPushButton('← Previous clip')
        self.next = QPushButton('Next clip →')
        self.previous.setAutoDefault(False)
        self.next.setAutoDefault(False)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 100000)
        self.scrub.setEnabled(False)
        self.position = QLabel('00:00:00.000')
        scrub_row.addWidget(self.previous)
        scrub_row.addWidget(self.scrub, 1)
        scrub_row.addWidget(self.position)
        scrub_row.addWidget(self.next)
        layout.addLayout(scrub_row)
        split = QSplitter(Qt.Horizontal)
        cards_panel = QWidget()
        cards_layout = QVBoxLayout(cards_panel)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        filters = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['Timeline order', 'Browse by camera / source'])
        self.sources = QComboBox()
        self.sources.addItem('All sources')
        filters.addWidget(self.mode)
        filters.addWidget(self.sources, 1)
        cards_layout.addLayout(filters)
        self.cards = QListWidget()
        self.cards.setViewMode(QListWidget.IconMode)
        self.cards.setResizeMode(QListWidget.Adjust)
        self.cards.setMovement(QListWidget.Static)
        self.cards.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cards.setIconSize(QSize(240, 135))
        self.cards.setGridSize(QSize(266, 220))
        self.cards.setWordWrap(True)
        self.cards.setSpacing(5)
        cards_layout.addWidget(self.cards, 1)
        split.addWidget(cards_panel)
        viewer = QWidget()
        viewer_layout = QVBoxLayout(viewer)
        viewer_layout.setContentsMargins(8, 0, 0, 0)
        self.image = FrameLabel('Select a clip to see a larger frame')
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(220, 124)
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image.setStyleSheet('background: #14243a; color: white; border-radius: 5px;')
        viewer_layout.addWidget(self.image, 2)
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_scroll = QScrollArea()
        info_scroll.setWidgetResizable(True)
        info_scroll.setMinimumHeight(0)
        info_scroll.setFrameShape(QScrollArea.NoFrame)
        info_scroll.setWidget(info)
        viewer_layout.addWidget(info_scroll, 2)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextFormat(Qt.PlainText)
        self.description.setMaximumHeight(150)
        info_layout.addWidget(self.description)
        self.include = QCheckBox('Include this clip in the exported timeline')
        self.include.setEnabled(False)
        info_layout.addWidget(self.include)
        self.edit_actions = QWidget()
        actions = QHBoxLayout(self.edit_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        self.edit_date = QPushButton('Edit date…')
        self.correct_source = QPushButton('Correct source clock…')
        for button in (self.edit_date, self.correct_source):
            button.setAutoDefault(False)
            button.setEnabled(False)
            actions.addWidget(button)
        self.edit_date.clicked.connect(self.editRequested)
        self.correct_source.clicked.connect(self.correctionRequested)
        info_layout.addWidget(self.edit_actions)
        self.hint = QLabel('Scrub or click the strip to inspect still frames. Sound and continuous playback must be checked in Premiere. Folder groups are sources, not confirmed camera identities.')
        self.hint.setWordWrap(True)
        info_layout.addWidget(self.hint)
        info_layout.addStretch(1)
        split.addWidget(viewer)
        split.setSizes([650, 340])
        layout.addWidget(split, 1)
        self._pixmap = QPixmap()
        self.seek_timer = QTimer(self)
        self.seek_timer.setSingleShot(True)
        self.seek_timer.setInterval(160)
        self.seek_timer.timeout.connect(self._seek)
        self.visible_timer = QTimer(self)
        self.visible_timer.setSingleShot(True)
        self.visible_timer.setInterval(40)
        self.visible_timer.timeout.connect(self._request_visible)
        self.cards.verticalScrollBar().valueChanged.connect(lambda _: self.visible_timer.start())
        self.cards.currentItemChanged.connect(self._select_card)
        self.mode.currentIndexChanged.connect(self._populate_cards)
        self.sources.currentIndexChanged.connect(self._populate_cards)
        self.scrub.valueChanged.connect(self._scrub_changed)
        self.strip.seek.connect(lambda fraction: self.scrub.setValue(round(fraction * self.scrub.maximum())))
        self.previous.clicked.connect(lambda: self._step(-1))
        self.next.clicked.connect(lambda: self._step(1))
        self.include.toggled.connect(self._include_changed)

    def set_clips(self, videos, excluded_paths=()):
        self.generation += 1
        self.seek_timer.stop()
        self.service.stop()
        self.videos = list(videos)
        self.excluded = set(excluded_paths)
        self.clips = chronological_sort([v for v in videos if v.path not in self.excluded])
        self.spans = []
        try:
            rate = timeline_rate(self.clips[0])[0][2]
            self.spans = [(float(start / rate), float(end / rate))
                          for start, end in assembly_frame_spans(self.clips, rate)]
        except (IndexError, ValueError, TypeError, OverflowError):
            pass
        self.strip.clips, self.strip.spans = self.clips, self.spans
        self.strip.update()
        self.scrub.setEnabled(bool(self.spans))
        sources = sorted({v.camera or 'Unknown' for v in videos}, key=str.casefold)
        current = self.sources.currentText()
        self.sources.blockSignals(True)
        self.sources.clear()
        self.sources.addItem('All sources')
        self.sources.addItems(sources)
        self.sources.setCurrentIndex(max(0, self.sources.findText(current)))
        self.sources.blockSignals(False)
        total = clock(self.spans[-1][1]) if self.spans else 'duration unavailable'
        self.summary.setText(f'{len(self.clips)} included clips · {len(sources)} automatic/manual sources · {total}\n'
                             'This is the XML assembly order: clips join end-to-end, with recording gaps removed. '
                             'Source browsing changes the cards, not the exported order.')
        self._populate_cards()

    def _populate_cards(self, *_args):
        self.cards.blockSignals(True)
        self.cards.clear()
        self.items.clear()
        self.requested.clear()
        numbers = {v.path: index for index, v in enumerate(self.clips)}
        source_mode = self.mode.currentIndex() == 1
        entries = sorted(self.videos, key=lambda v: ((v.camera or '').casefold(), v.filename.casefold(), v.path)) if source_mode else self.clips
        placeholder = QPixmap(240, 135)
        placeholder.fill(QColor('#dce3eb'))
        for video in entries:
            if self.sources.currentIndex() and video.camera != self.sources.currentText():
                continue
            index = numbers.get(video.path)
            start = clock(self.spans[index][0]) if index is not None and self.spans else 'Time unavailable'
            order = f'#{index + 1} · {start}' if index is not None else 'Excluded from timeline'
            item = QListWidgetItem(QIcon(placeholder), f'{order}\n{video.camera or "Unknown"}\n{video.filename}')
            item.setData(Qt.UserRole, video.path)
            item.setToolTip(video.path)
            item.setForeground(source_color(video.camera))
            item.setSizeHint(QSize(256, 210))
            self.cards.addItem(item)
            self.items[video.path] = item
        self.cards.blockSignals(False)
        selected = self.items.get(self.current_path)
        if selected is None and self.cards.count():
            selected = self.cards.item(0)
        if selected:
            self.cards.setCurrentItem(selected)
        else:
            self.current_path = None
            self.include.setEnabled(False)
            self.edit_date.setEnabled(False)
            self.correct_source.setEnabled(False)
            self._pixmap = QPixmap()
            self.image.clear()
            self.image.setText('No clips in this view. Browse by source to restore excluded clips.')
            self.description.clear()
        self.visible_timer.start()

    def _request_visible(self):
        if not self.isVisible():
            return
        viewport = self.cards.viewport().rect()
        videos = {v.path: v for v in self.videos}
        for path, item in self.items.items():
            if path not in self.requested and self.cards.visualItemRect(item).intersects(viewport):
                self.requested.add(path)
                video = videos[path]
                sample = min(2., max(0., (video.duration_seconds or 0) * .1))
                self.service.request(video, sample, ('card', self.generation, path))

    def _select_card(self, item, _previous):
        if item is None:
            return
        path = item.data(Qt.UserRole)
        video = next(v for v in self.videos if v.path == path)
        self._select_video(video)

    def _select_video(self, video):
        path = video.path
        self._show_video(video, 0.)
        if path in self.excluded:
            self.position.setText('Excluded clip')
        for index, clip in enumerate(self.clips):
            if clip.path == path and self.spans:
                self.scrub.blockSignals(True)
                self.scrub.setValue(round(self.spans[index][0] / self.spans[-1][1] * self.scrub.maximum()))
                self.scrub.blockSignals(False)
                self.strip.position = self.spans[index][0]
                self.position.setText(clock(self.strip.position))
                self.strip.update()
                break

    def _show_video(self, video, seconds):
        self.current_path = video.path
        self.clipSelected.emit(video.path)
        self.include.blockSignals(True)
        self.include.setChecked(video.path not in self.excluded)
        self.include.setEnabled(True)
        self.edit_date.setEnabled(True)
        self.correct_source.setEnabled(bool(video.camera))
        self.include.blockSignals(False)
        stamp = video.selected_timestamp
        date = stamp.normalized.isoformat(timespec='seconds') if stamp and stamp.normalized else 'No capture date — placed last'
        warning = ('\n' + '\n'.join(video.warnings[:3])) if video.warnings else ''
        self.description.setText(f'{video.filename}\n{video.camera or "Unknown"}\nCapture: {date}\n'
                                 f'Clip frame at {clock(seconds)}{warning}')
        self.description.setToolTip('\n'.join(video.warnings))
        self._pixmap = QPixmap()
        self.image.clear()
        self.image.setText('Loading frame…')
        self.frame_token += 1
        self.service.discard_pending('viewer')
        self.service.request(video, seconds, ('viewer', self.generation, self.frame_token), priority=True)

    def _frame_ready(self, token, image, message):
        kind, generation, key = token
        if generation != self.generation:
            return
        if kind == 'card':
            item = self.items.get(key)
            if item is not None:
                if not image.isNull():
                    item.setIcon(QIcon(QPixmap.fromImage(image)))
                else:
                    item.setToolTip(item.toolTip() + '\n' + message)
        elif key == self.frame_token:
            if image.isNull():
                self.image.setText(message)
            else:
                self._pixmap = QPixmap.fromImage(image)
                self._scale_image()

    def _scale_image(self):
        if not self._pixmap.isNull():
            self.image.frame = self._pixmap
            self.image.update()

    def _scrub_changed(self):
        if self.spans:
            self.strip.position = self.scrub.value() / self.scrub.maximum() * self.spans[-1][1]
            self.position.setText(clock(self.strip.position))
            self.strip.update()
            self.seek_timer.start()

    def _seek(self):
        if not self.spans:
            return
        position = self.strip.position
        index = min(len(self.clips) - 1, bisect_right([end for _, end in self.spans], position))
        video = self.clips[index]
        seconds = max(0., min(position - self.spans[index][0], max(0., (video.duration_seconds or 0) - .05)))
        item = self.items.get(video.path)
        if item:
            self.cards.blockSignals(True)
            self.cards.setCurrentItem(item)
            self.cards.scrollToItem(item)
            self.cards.blockSignals(False)
        self._show_video(video, seconds)

    def _step(self, delta):
        if not self.clips:
            return
        current = next((i for i, v in enumerate(self.clips) if v.path == self.current_path), 0)
        index = max(0, min(len(self.clips) - 1, current + delta))
        item = self.items.get(self.clips[index].path)
        if item:
            self.cards.blockSignals(True)
            self.cards.setCurrentItem(item)
            self.cards.scrollToItem(item)
            self.cards.blockSignals(False)
        self._select_video(self.clips[index])

    def _include_changed(self, checked):
        if self.current_path:
            self.inclusionChanged.emit(self.current_path, checked)

    def showEvent(self, event):
        super().showEvent(event)
        self.visible_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_image()
        self.visible_timer.start()

    def stop(self):
        self.seek_timer.stop()
        self.visible_timer.stop()
        self.service.stop()
        self.requested.clear()

    def resume(self):
        self.visible_timer.start()
        if self._pixmap.isNull() and self.current_path:
            video = next((v for v in self.videos if v.path == self.current_path), None)
            if video:
                self._show_video(video, 0.)
