#!/usr/bin/env python3
"""Regenerate the existing #1904 30-file recipe; fail on missing encoders or failed files."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://github.com/amule-org/amule/pull/1904#issuecomment-6188072318'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    out = args.directory.resolve()
    out.mkdir(parents=True, exist_ok=True)
    variables = {
        '$V10': shlex.split('-f lavfi -i testsrc2=size=320x240:rate=25:duration=10'),
        '$V61': shlex.split('-f lavfi -i testsrc2=size=320x240:rate=25:duration=61.5'),
        '$A10': shlex.split('-f lavfi -i sine=frequency=440:sample_rate=48000:duration=10'),
        '$A61': shlex.split('-f lavfi -i sine=frequency=440:sample_rate=44100:duration=61.5'),
        '${T[@]}': ['-metadata', 'artist=Spike Artist', '-metadata', 'title=Spike Title',
                     '-metadata', 'album=Spike Album'],
    }
    base = [args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y']
    cover = base + ['-f', 'lavfi', '-i', 'testsrc2=size=300x300:duration=1',
                    '-frames:v', '1', '-threads', '2', 'cover.jpg']
    subprocess.run(cover, cwd=out, check=True, capture_output=True, timeout=30)
    cases = []
    for line in (ROOT / 'benchmarks/reference/gen_corpus_original.sh').read_text().splitlines():
        if not line.startswith('g '):
            continue
        _, name, *tokens = shlex.split(line)
        options = []
        for token in tokens:
            options += variables.get(token, [token])
        # Only bound generator concurrency, preserving the media inputs and encoder choices.
        options += ['-threads', '2']
        if 'libx265' in options:
            options += ['-x265-params', 'pools=2:frame-threads=2']
        if 'libsvtav1' in options:
            options += ['-svtav1-params', 'lp=2']
        command = base + options + [name]
        print(name, flush=True)
        result = subprocess.run(command, cwd=out, capture_output=True, timeout=180)
        if result.returncode:
            raise SystemExit(result.stderr.decode(errors='replace'))
        expected_codec = {
            1: 'h264', 2: 'hevc', 3: 'vp9', 4: 'av1', 5: 'mpeg4', 6: 'mpeg4',
            7: 'mpeg2video', 8: 'mpeg1video', 9: 'h264', 10: 'h264', 11: 'wmv2',
            12: 'theora', 13: 'h264', 14: 'h264', 15: 'prores', 16: 'mjpeg',
            17: 'h263', 18: 'mp3', 19: 'mp3', 20: 'mp3', 21: 'flac', 22: 'vorbis',
            23: 'opus', 24: 'aac', 25: 'pcm_s16le', 26: 'pcm_s16be', 27: 'eac3',
            28: 'dts', 29: 'h264', 30: 'aac'}[int(name[:2])]
        seconds = 62 if int(name[:2]) in [1, 5, 18, 19, 20, 21, 22, 23, 24, 30] else 10
        if name.startswith('15-'):
            seconds = 3
        # Raw AVC has no independently established stream timeline; unknown is intentional.
        if name.startswith('29-'):
            seconds = None
        data = (out / name).read_bytes()
        cases.append(dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                          expected_codec=expected_codec, expected_seconds=seconds, command=command))
    if len(cases) != 30:
        raise SystemExit(f'Expected 30 cases, generated {len(cases)}')
    (out / 'cover.jpg').unlink()
    manifest = dict(origin=ORIGIN, generator=subprocess.check_output(
        [args.ffmpeg, '-version'], text=True).splitlines()[0],
        changes='Generator thread limits only; regenerated artifacts, not original binaries.', cases=cases)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
