"""One asynchronous decoder at a time, with a bounded in-memory frame cache."""
from collections import OrderedDict, deque
import os
import shutil

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtGui import QImage

from app.core.metadata_extractor import _bundled_tool


class ThumbnailService(QObject):
    ready = Signal(object, QImage, str)

    def __init__(self, parent=None, executable=None):
        super().__init__(parent)
        self.executable = executable or _bundled_tool('ffmpeg') or shutil.which('ffmpeg')
        self.cache = OrderedDict()
        self.queue = deque()
        self.waiters = {}
        self.active = None
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.buffer = bytearray()

    def request(self, video, seconds, token, *, priority=False):
        try:
            stat = os.stat(video.path)
        except OSError:
            self.ready.emit(token, QImage(), 'Media file unavailable at the saved path')
            return
        if not self.executable:
            self.ready.emit(token, QImage(), 'Install FFmpeg to see clip images. XML export remains available.')
            return
        # Never cache media frames on disk or include them in session reports.
        key = (video.path, stat.st_size, stat.st_mtime_ns, round(max(0, seconds), 3))
        if key in self.cache:
            self.cache.move_to_end(key)
            self.ready.emit(token, self.cache[key], '')
            return
        if key in self.waiters:
            self.waiters[key].append(token)
            if priority and key in self.queue:
                self.queue.remove(key)
                self.queue.appendleft(key)
            return
        self.waiters[key] = [token]
        (self.queue.appendleft if priority else self.queue.append)(key)
        QTimer.singleShot(0, self._next)

    def _next(self):
        if self.active is not None or not self.queue:
            return
        self.active = self.queue.popleft()
        self.buffer.clear()
        path, _, _, seconds = self.active
        self.process.start(str(self.executable), [
            '-hide_banner', '-loglevel', 'error', '-nostdin', '-threads', '1',
            '-ss', str(seconds), '-protocol_whitelist', 'file,pipe,crypto', '-i', path,
            '-map', '0:v:0', '-frames:v', '1', '-an', '-sn', '-dn',
            '-vf', 'scale=640:360:force_original_aspect_ratio=decrease',
            '-threads', '1', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'])
        self.timer.start(15000)

    def discard_pending(self, kind):
        """Drop superseded scrub positions instead of decoding every slider move."""
        for key in list(self.waiters):
            tokens = [token for token in self.waiters[key] if not isinstance(token, tuple) or token[0] != kind]
            if tokens or key == self.active:
                self.waiters[key] = tokens
            else:
                self.waiters.pop(key)
                if key in self.queue:
                    self.queue.remove(key)

    def _read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.buffer) > 2 * 1024 * 1024:
            self.process.kill()

    def _finished(self, code, _status):
        self._read()
        image = QImage.fromData(bytes(self.buffer)) if code == 0 else QImage()
        self._complete(image, '' if not image.isNull() else 'Frame unavailable — the clip may be unreadable or unsupported')

    def _error(self, error):
        if error == QProcess.FailedToStart:
            self._complete(QImage(), 'FFmpeg could not start. Check the installed preview tools.')

    def _timeout(self):
        self.process.kill()

    def _complete(self, image, message):
        if self.active is None:
            return
        self.timer.stop()
        key, self.active = self.active, None
        if not image.isNull():
            self.cache[key] = image
            while len(self.cache) > 48:
                self.cache.popitem(last=False)
        for token in self.waiters.pop(key, []):
            self.ready.emit(token, image, message)
        QTimer.singleShot(0, self._next)

    def stop(self):
        self.queue.clear()
        self.waiters.clear()
        self.active = None
        self.timer.stop()
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
