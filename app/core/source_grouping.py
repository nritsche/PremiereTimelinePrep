"""Evidence-based camera labels, with explicit folder-source fallbacks."""
from pathlib import Path
import re


def camera_identity(exif, format_tags):
    fields = {}
    for key, value in exif.items():
        if isinstance(value, (str, int)) and str(value).strip():
            fields.setdefault(key.rsplit(':', 1)[-1].casefold(), str(value).strip())
    for key, value in format_tags.items():
        if isinstance(value, str) and value.strip():
            fields.setdefault(key.rsplit('.', 1)[-1].casefold(), value.strip())
    make = fields.get('make', '')
    model = fields.get('model') or fields.get('cameramodelname', '')
    serial = fields.get('bodyserialnumber') or fields.get('cameraserialnumber') or fields.get('serialnumber')
    parts = [model] if make and model.casefold().startswith(make.casefold()) else [make, model]
    label = ' '.join(part for part in parts if part)
    if serial and label:
        label += ' · ' + serial
    return label or None


def _source_folder(path):
    folder = Path(path).parent
    # Skip standard card directories so Camera A/DCIM/100MEDIA stays Camera A.
    while folder.parent != folder and (folder.name.casefold() in
            {'dcim', 'private', 'avchd', 'bdmv', 'stream', 'clips', 'clip', 'mproot'}
            or re.fullmatch(r'\d{3}[a-zA-Z_]+', folder.name)):
        folder = folder.parent
    return folder


def assign_automatic_sources(videos):
    """Retain existing/manual labels; never infer physical identity from a codec."""
    folders = {_source_folder(video.path) for video in videos if not video.camera}
    labels = {}
    for folder in folders:
        parts = folder.parts
        suffix = str(folder)
        for depth in range(1, len(parts) + 1):
            suffix = '/'.join(parts[-depth:])
            if sum('/'.join(other.parts[-depth:]) == suffix for other in folders) == 1:
                break
        labels[folder] = 'Folder: ' + (suffix or str(folder))
    for video in videos:
        if not video.camera:
            video.camera = camera_identity(video.metadata.get('exiftool.raw', {}),
                                           video.metadata.get('ffprobe.format', {}).get('tags', {}))
            if video.camera:
                video.metadata['source_group_basis'] = 'Embedded camera metadata'
            else:
                video.camera = labels[_source_folder(video.path)]
                video.metadata['source_group_basis'] = 'Folder source; camera identity unavailable'
