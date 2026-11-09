"""Compare a candidate probe with the reference on synthetic media, never user files.

This is a regression gate for packaging changes, not a claim of universal format
support. See https://ffmpeg.org/ffmpeg-codecs.html for the fixture encoders.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


FIXTURES = [
    ('h264.mp4', 'libx264', 'aac', ['-preset', 'ultrafast']),
    ('hevc.mp4', 'libx265', 'aac', ['-preset', 'ultrafast', '-x265-params', 'pools=1:log-level=error']),
    ('prores.mov', 'prores_ks', 'pcm_s16le', ['-pix_fmt', 'yuv422p10le']),
    ('mpeg4.mp4', 'mpeg4', 'aac', []),
    ('mpeg2.mpg', 'mpeg2video', 'mp2', []),
    ('mjpeg.avi', 'mjpeg', 'pcm_s16le', ['-pix_fmt', 'yuvj420p']),
    ('vp9.webm', 'libvpx-vp9', 'libopus', ['-deadline', 'realtime', '-cpu-used', '8']),
    ('av1.mkv', 'libaom-av1', 'flac', ['-cpu-used', '8', '-row-mt', '1']),
]


def run(command):
    return subprocess.run([str(arg) for arg in command], check=True, timeout=120,
                          capture_output=True, text=True, encoding='utf-8', errors='replace').stdout


def probe(executable, media):
    return json.loads(run([executable, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', media]))


def differences(reference, candidate, path=''):
    """Compare all reported metadata, except human-readable codec descriptions.

    --enable-small builds omit codec_long_name, which the app does not use for
    timestamp selection, media validation or XML. All tags and side data remain
    significant, including fields not currently consumed by the app.
    """
    if isinstance(reference, dict) and isinstance(candidate, dict):
        result = []
        for key in sorted((reference.keys() | candidate.keys()) - {'codec_long_name'}):
            child = path + '/' + key
            if key not in reference or key not in candidate:
                result.append(child)
            else:
                result.extend(differences(reference[key], candidate[key], child))
        return result
    if isinstance(reference, list) and isinstance(candidate, list):
        if len(reference) != len(candidate):
            return [path + '/length']
        return [item for index, (a, b) in enumerate(zip(reference, candidate))
                for item in differences(a, b, path + '/' + str(index))]
    return [] if reference == candidate else [path]


def check(ffmpeg, reference, candidate, directory):
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for filename, video_codec, audio_codec, options in FIXTURES:
        media = directory / filename
        row = {'fixture': filename, 'success': False}
        try:
            run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                 '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=30000/1001',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                 '-t', '0.25', '-threads', '1', '-c:v', video_codec, *options,
                 '-c:a', audio_codec, '-metadata', 'creation_time=2026-01-02T03:04:05Z', media])
            expected = probe(reference, media)
            streams = expected.get('streams', [])
            if {stream.get('codec_type') for stream in streams} != {'video', 'audio'}:
                raise ValueError('Reference fixture must contain both video and audio')
            row['differences'] = differences(expected, probe(candidate, media))
            row['success'] = not row['differences']
        except (subprocess.SubprocessError, ValueError, OSError) as error:
            row['error'] = str(error)
            if isinstance(error, subprocess.CalledProcessError):
                row['stderr'] = error.stderr[-4000:]
        rows.append(row)
    return {'schema_version': 1, 'success': all(row['success'] for row in rows),
            'candidate_sha256': hashlib.sha256(Path(candidate).read_bytes()).hexdigest(),
            'reference_sha256': hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
            'scope': 'Synthetic fixtures only; real camera media and Premiere validation remain required.',
            'fixtures': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg'))
    parser.add_argument('--reference', default=shutil.which('ffprobe'))
    parser.add_argument('--candidate', type=Path,
                        default=Path('dist/PremiereTimelinePrep/_internal/tools/ffprobe/ffprobe.exe'))
    parser.add_argument('--directory', type=Path, default=Path('build-tools/compatibility-media'))
    parser.add_argument('--report', type=Path, default=Path('build-tools/ffprobe-compatibility.json'))
    args = parser.parse_args()
    if not args.ffmpeg or not args.reference:
        parser.error('Both reference FFmpeg and FFprobe are required')
    report = check(args.ffmpeg, args.reference, args.candidate, args.directory)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not report['success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
