"""Background directory walk and media metadata scan."""
import os
from zoneinfo import ZoneInfo

from PySide6.QtCore import QThread, Signal

from app.core.metadata_extractor import ScanCancelled, extract_video
from app.core.scanner import discover_videos
from app.models.video_file import VideoFile


class ScanWorker(QThread):
    progress = Signal(int, int)
    status = Signal(str)
    completed = Signal(list)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, folders, extensions, recursive, timezone_name="UTC"):
        super().__init__()
        self.folders = list(folders)
        self.extensions = list(extensions)
        self.recursive = recursive
        self.timezone_name = timezone_name

    def run(self):
        try:
            self.status.emit("Finding video files…")
            errors = []
            paths = list(discover_videos(self.folders, self.extensions, self.recursive,
                                        cancelled=self.isInterruptionRequested, on_error=errors.append))
            if errors:
                raise OSError("\n".join(str(error) for error in errors))
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
        except Exception as exc:
            self.failed.emit("Folder scan error: {}".format(exc))
            return
        videos = []
        total = len(paths)
        if not total:
            self.completed.emit(videos)
            return
        for index, path in enumerate(paths, 1):
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            self.status.emit("Analyzing {}".format(os.path.basename(path)))
            try:
                video = extract_video(path, cancelled=self.isInterruptionRequested,
                                      default_timezone=ZoneInfo(self.timezone_name))
            except ScanCancelled:
                self.cancelled.emit()
                return
            except Exception as exc:
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                video = VideoFile(path=os.path.abspath(path), filename=os.path.basename(path),
                                  size_bytes=size, error=str(exc),
                                  warnings=["Could not analyze this file: {}".format(exc)])
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            videos.append(video)
            self.progress.emit(index, total)
        self.completed.emit(videos)
