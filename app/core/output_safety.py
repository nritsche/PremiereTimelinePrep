"""Protect source media from export destinations, including aliases."""
import os
from pathlib import Path


def check_output_path(path, videos):
    target = Path(path).resolve()
    for video in videos:
        source = Path(video.path).resolve()
        same = target == source
        if not same and target.exists() and source.exists():
            same = os.path.samefile(target, source)
        if same:
            raise ValueError("Export destination is a source media file. Choose a different filename.")
