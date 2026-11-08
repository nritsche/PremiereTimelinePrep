"""Experimental Final Cut Pro 7 XML timeline interchange."""
from fractions import Fraction
import math
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from app.core.chronological_sorter import chronological_sort


def _rate(value):
    if not value or not math.isfinite(value) or value <= 0:
        raise ValueError("A valid frame rate is required; rescan with FFprobe installed")
    for base in (24, 30, 60, 120):
        if abs(value - base * 1000 / 1001) < .002:
            return base, True, Fraction(base * 1000, 1001)
    if abs(value - round(value)) < .002:
        return round(value), False, Fraction(round(value))
    raise ValueError("Unsupported frame rate: {}".format(value))


def timeline_rate(video):
    """Return an XML-representable timebase plus an explicit approximation notice.

    r_frame_rate is a guess, so only prefer it when close to the average.
    Otherwise use the nearest standard rate within 1%, or nearest integer.
    This describes elapsed time; it does not convert VFR media to CFR.
    """
    average = video.frame_rate
    if not average or not math.isfinite(average) or average < 1 or average > 240:
        raise ValueError("{}: frame rate must be between 1 and 240 fps".format(video.filename))
    try:
        return _rate(average), None
    except ValueError:
        pass
    chosen = None
    try:
        nominal = float(Fraction(video.metadata.get("ffprobe.r_frame_rate", "0/1")))
        if abs(nominal - average) / average <= .02:
            chosen = _rate(nominal)
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    if chosen is None:
        standards = [Fraction(rate) for rate in (12, 15, 24, 25, 30, 48, 50, 60, 100, 120, 240)]
        standards += [Fraction(base * 1000, 1001) for base in (24, 30, 60, 120)]
        nearest = min(standards, key=lambda value: abs(float(value) - average))
        chosen = _rate(float(nearest) if abs(float(nearest) - average) / average <= .01 else round(average))
    notice = "{}: reported {:.6f} fps; XML uses {:.6f} fps. Variable/nonstandard timing is approximate; verify playback and audio sync in Premiere.".format(video.filename, average, float(chosen[2]))
    return chosen, notice


def timeline_rate_notices(videos, excluded_paths=()):
    excluded = set(excluded_paths)
    return [notice for video in videos if video.path not in excluded
            for _, notice in [timeline_rate(video)] if notice]


def _text(parent, name, value):
    child = ET.SubElement(parent, name)
    child.text = str(value)
    return child


def _write_rate(parent, rate):
    node = ET.SubElement(parent, "rate")
    _text(node, "timebase", rate[0])
    _text(node, "ntsc", "TRUE" if rate[1] else "FALSE")


def write_timeline_xml(path, videos, *, excluded_paths=(), name="Chronological footage"):
    """Write a contiguous assembly with linked video and per-channel audio.

    Sequence settings follow the first included clip. Source and sequence frame
    counts use their own rates; capture times determine ordering, not gaps.
    """
    excluded = set(excluded_paths)
    clips = chronological_sort([v for v in videos if v.path not in excluded])
    if not clips:
        raise ValueError("Include at least one clip before exporting")
    rates = []
    for video in clips:
        if video.error or not video.duration_seconds or not math.isfinite(video.duration_seconds) or video.duration_seconds <= 0:
            raise ValueError("{}: valid media duration is required; rescan with FFprobe".format(video.filename))
        if not video.width or not video.height:
            raise ValueError("{}: video dimensions are missing; rescan with FFprobe".format(video.filename))
        if not Path(video.path).is_absolute():
            raise ValueError("Media paths must be absolute")
        rates.append(timeline_rate(video)[0])
        if video.audio_codec and not video.metadata.get("ffprobe.audio_channels"):
            raise ValueError("{}: audio channel details are missing; rescan before XML export".format(video.filename))
    root = ET.Element("xmeml", version="5")
    sequence = ET.SubElement(root, "sequence", id="sequence-1")
    _text(sequence, "name", name)
    sequence_rate = rates[0]
    _write_rate(sequence, sequence_rate)
    media = ET.SubElement(sequence, "media")
    video_media = ET.SubElement(media, "video")
    sample = ET.SubElement(ET.SubElement(video_media, "format"), "samplecharacteristics")
    _write_rate(sample, sequence_rate)
    for key, value in (("width", clips[0].width), ("height", clips[0].height),
                       ("anamorphic", "FALSE"), ("pixelaspectratio", "square"), ("fielddominance", "none")):
        _text(sample, key, value)
    video_track = ET.SubElement(video_media, "track")
    audio_media = ET.SubElement(media, "audio")
    audio_tracks = []
    elapsed = Fraction(0)
    for index, (video, rate) in enumerate(zip(clips, rates), 1):
        source_frames = max(1, round(Fraction(str(video.duration_seconds)) * rate[2]))
        start = round(elapsed * sequence_rate[2])
        elapsed += Fraction(str(video.duration_seconds))
        end = max(start + 1, round(elapsed * sequence_rate[2]))
        if index > 1:
            start = previous_end
            end = max(start + 1, end)
        previous_end = end
        channels = int(video.metadata.get("ffprobe.audio_channels", 0)) if video.audio_codec else 0
        if channels < 0 or channels > 32:
            raise ValueError("Unsupported audio channel count")
        while len(audio_tracks) < channels:
            audio_tracks.append(ET.SubElement(audio_media, "track"))
        ids = ["video-{}".format(index)] + ["audio-{}-{}".format(index, ch + 1) for ch in range(channels)]
        for channel in range(channels + 1):
            item = ET.SubElement(video_track if channel == 0 else audio_tracks[channel - 1], "clipitem", id=ids[channel])
            _text(item, "name", video.filename)
            _write_rate(item, rate)
            for key, value in (("duration", source_frames), ("start", start), ("end", end), ("in", 0), ("out", source_frames)):
                _text(item, key, value)
            file = ET.SubElement(item, "file", id="file-{}".format(index))
            if channel == 0:
                _text(file, "name", video.filename)
                _text(file, "pathurl", Path(video.path).as_uri())
                _write_rate(file, rate)
                _text(file, "duration", source_frames)
                file_media = ET.SubElement(file, "media")
                characteristics = ET.SubElement(ET.SubElement(file_media, "video"), "samplecharacteristics")
                _write_rate(characteristics, rate)
                _text(characteristics, "width", video.width)
                _text(characteristics, "height", video.height)
                if channels:
                    audio = ET.SubElement(file_media, "audio")
                    _text(audio, "channelcount", channels)
                    audio_sample = ET.SubElement(audio, "samplecharacteristics")
                    _text(audio_sample, "samplerate", video.metadata.get("ffprobe.audio_sample_rate", 48000))
            if channel:
                source = ET.SubElement(item, "sourcetrack")
                _text(source, "mediatype", "audio")
                _text(source, "trackindex", channel)
            for linked_channel, linked_id in enumerate(ids):
                link = ET.SubElement(item, "link")
                _text(link, "linkclipref", linked_id)
                _text(link, "mediatype", "video" if linked_channel == 0 else "audio")
                _text(link, "trackindex", max(1, linked_channel))
                _text(link, "clipindex", index if linked_channel == 0 else sum(1 for prev in clips[:index] if prev.audio_codec and int(prev.metadata.get("ffprobe.audio_channels", 0)) >= linked_channel))
    _text(sequence, "duration", end)
    notices = timeline_rate_notices(clips)
    if notices:
        _text(ET.SubElement(sequence, "logginginfo"), "lognote", "\n".join(notices))
    ET.indent(root)
    data = b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding="utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=Path(path).parent, delete=False) as stream:
            temporary = stream.name
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
