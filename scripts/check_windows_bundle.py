"""Run the actual Windows executable against generated, non-private media."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    dist = Path('dist/PremiereTimelinePrep').resolve()
    sample = Path('build-tools/self-test.mp4').resolve()
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is needed on the build runner to create synthetic test media')
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=25',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                    '-t', '1', '-c:v', 'mpeg4', '-c:a', 'aac', str(sample)], check=True)
    result = dist / 'self-test.json'
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    subprocess.run([str(dist / 'PremiereTimelinePrep.exe'), '--self-test', str(result), '--media', str(sample)],
                   check=True, timeout=120, env=environment)
    payload = json.loads(result.read_text(encoding='utf-8'))
    if payload.get('success') is not True:
        raise RuntimeError(payload)
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
