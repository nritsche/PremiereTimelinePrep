"""Portable models used by scanning and timestamp resolution."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TimestampCandidate:
    source: str
    raw_value: str
    normalized: Optional[datetime]
    confidence: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class VideoFile:
    path: str
    filename: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    frame_rate: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    camera: Optional[str] = None
    timestamp_candidates: List[TimestampCandidate] = field(default_factory=list)
    selected_timestamp: Optional[TimestampCandidate] = None
    filesystem_created: Optional[datetime] = None
    filesystem_modified: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
