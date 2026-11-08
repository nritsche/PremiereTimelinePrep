"""Recursive media discovery with overlap and hard-link de-duplication."""
import os
from typing import Iterable, Iterator, List, Optional, Set, Tuple

DEFAULT_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".3gp", ".webm"}


def discover_videos(folders: Iterable[str], extensions: Optional[Iterable[str]] = None,
                    recursive: bool = True) -> Iterator[str]:
    allowed = {e.lower() if e.startswith(".") else "." + e.lower() for e in (extensions or DEFAULT_EXTENSIONS)}
    seen: Set[Tuple[object, ...]] = set()
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        walker = os.walk(folder) if recursive else ((folder, [], os.listdir(folder)),)
        for root, _, names in walker:
            for name in names:
                path = os.path.join(root, name)
                if os.path.splitext(name)[1].lower() not in allowed or not os.path.isfile(path):
                    continue
                try:
                    stat = os.stat(path)
                    identity = (stat.st_dev, stat.st_ino) if stat.st_ino else (os.path.normcase(os.path.realpath(path)),)
                except OSError:
                    identity = (os.path.normcase(os.path.realpath(path)),)
                if identity in seen:
                    continue
                seen.add(identity)
                yield os.path.abspath(path)
