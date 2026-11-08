"""Background directory walk and media metadata scan."""
import os

from PySide6.QtCore import QThread, Signal

from app.core.metadata_extractor import extract_video
from app.core.scanner import discover_videos
from app.models.video_file import VideoFile


class ScanWorker(QThread):
    progress = Signal(int, int)
    status = Signal(str)
    completed = Signal(list)

    def __init__(self, folders, extensions, recursive):
        super().__init__()
        self.folders = list(folders)
        self.extensions = list(extensions)
        self.recursive = recursive

    def run(self):
        try:
            self.status.emit("Finding video files…")
            paths = list(discover_videos(self.folders, self.extensions, self.recursive))
        except Exception as exc:
            self.status.emit("Folder scan error: {}".format(exc))
            paths = []
        videos = []
        total = len(paths)
        if not total:
            self.completed.emit(videos)
            return
        for index, path in enumerate(paths, 1):
            if self.isInterruptionRequested():
                break
            self.status.emit("Analyzing {}".format(os.path.basename(path)))
            try:
                video = extract_video(path)
            except Exception as exc:
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                video = VideoFile(path=os.path.abspath(path), filename=os.path.basename(path),
                                  size_bytes=size, error=str(exc),
                                  warnings=["Could not analyze this file: {}".format(exc)])
            videos.append(video)
            self.progress.emit(index, total)
        self.completed.emit(videos)
