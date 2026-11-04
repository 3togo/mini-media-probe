#!/usr/bin/env python3
"""Compare matched ffprobe/helper builds on the checked 30-file corpus."""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('length_seconds', 'bitrate_kbps', 'codec', 'artist', 'album', 'title')
ENV = {k: v for k, v in os.environ.items()
       if k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy', 'ld_preload')}
ENTRIES = ('format=duration,bit_rate:format_tags=artist,album,title:'
           'stream=index,codec_name,codec_type:stream_disposition=attached_pic:'
           'stream_tags=artist,album,title')


def number(value, divisor=1, rounding=ROUND_FLOOR):
    try:
        value = Decimal(str(value)) / divisor
        if not value.is_finite() or value <= 0:
            return 0
        return int(min(Decimal(4294967295), value.to_integral_value(rounding=rounding)))
    except (InvalidOperation, ValueError, TypeError):
        return 0


def normalise_ffprobe(raw):
    """Apply the documented publishing policy, not a first-stream shortcut."""
    container = raw.get('format', {})
    streams = [s for s in sorted(raw.get('streams', []), key=lambda s: s.get('index', 0))
               if not s.get('disposition', {}).get('attached_pic', 0)]
    selected = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if selected is None:
        selected = next((s for s in streams if s.get('codec_type') == 'audio'), {})
    result = dict(length_seconds=number(container.get('duration'), rounding=ROUND_HALF_UP),
                  bitrate_kbps=number(container.get('bit_rate'), 1000),
                  codec=selected.get('codec_name', ''))
    tags = {k.lower(): v for k, v in container.get('tags', {}).items()}
    fallback = {k.lower(): v for k, v in selected.get('tags', {}).items()}
    for key in ('artist', 'album', 'title'):
        result[key] = tags.get(key, '')
        if not result[key] and result['codec'] in ('vorbis', 'opus', 'flac', 'speex'):
            result[key] = fallback.get(key, '')
    return result


def child_limits():
    # Match the helper's POSIX limits for this trusted corpus experiment.
    import resource
    for kind, limit in [(resource.RLIMIT_CPU, 25), (resource.RLIMIT_CORE, 0),
                        (resource.RLIMIT_FSIZE, 256 * 1024),
                        (resource.RLIMIT_AS, 1024 * 1024 * 1024)]:
        resource.setrlimit(kind, (limit, limit))


def invoke(command, path, ffprobe=False):
    kwargs = {'env': ENV, 'capture_output': True, 'timeout': 30}
    if ffprobe and os.name == 'posix':
        kwargs['preexec_fn'] = child_limits
    started = time.monotonic()
    with path.open('rb') as source:
        try:
            output = subprocess.run(command, stdin=source, **kwargs)
        except subprocess.TimeoutExpired:
            return dict(exit='timeout', metadata=None, raw=None, elapsed_ms=30000)
    metadata = None
    raw = None
    error = output.stderr.decode(errors='replace')
    if output.returncode == 0:
        try:
            raw = json.loads(output.stdout)
            metadata = normalise_ffprobe(raw) if ffprobe else {k: raw[k] for k in FIELDS}
        except (ValueError, KeyError, UnicodeError) as exc:
            error += str(exc)
    return dict(exit=output.returncode, metadata=metadata, raw=raw, stderr=error,
                elapsed_ms=(time.monotonic() - started) * 1000)


def fingerprint(path):
    data = path.read_bytes()
    return dict(bytes=len(data), gzip9_bytes=len(gzip.compress(data, compresslevel=9, mtime=0)),
                sha256=hashlib.sha256(data).hexdigest())


def version(command):
    return subprocess.check_output(command, text=True, env=ENV).splitlines()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['broad', 'common'], required=True)
    parser.add_argument('--corpus', type=Path, default=ROOT / '.cache/corpus')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    suffix = 'native-' + args.profile + '-matched'
    build = ROOT / ('build-' + suffix)
    ffbuild = ROOT / ('.cache/ffmpeg-' + suffix)
    prefix = ROOT / ('.cache/prefix-' + suffix)
    output = args.output or ROOT / ('reports/ffprobe-' + args.profile + '.json')
    stripped = ROOT / ('.cache/ffprobe-comparison-' + args.profile)
    stripped.mkdir(parents=True, exist_ok=True)
    commands = {}
    binaries = {}
    strip = shutil.which('strip')
    if not strip:
        raise SystemExit('strip is required for a stripped-executable comparison')
    for name in ('ffprobe', 'mini-media-probe'):
        target = stripped / name
        shutil.copy2(build / name, target)
        subprocess.run([strip, str(target)], check=True, env=ENV)
        binaries[name] = fingerprint(target)
        if name == 'ffprobe':
            commands[name] = [str(target), '-v', 'error', '-probesize', '5242880',
                              '-analyzeduration', '5000000', '-max_alloc', '134217728',
                              '-protocol_whitelist', 'fd', '-show_entries', ENTRIES,
                              '-of', 'json', 'fd:']
        else:
            commands[name] = [str(target), '--json']
    components = (ffbuild / 'config_components.h').read_text().splitlines()
    enabled = [line.split()[1].removeprefix('CONFIG_') for line in components
               if line.startswith('#define CONFIG_') and line.endswith(' 1')]
    for forbidden in ('_DECODER', '_ENCODER', '_MUXER', '_FILTER'):
        if any(name.endswith(forbidden) for name in enabled):
            raise SystemExit('Unexpected enabled component: ' + forbidden)
    if [name for name in enabled if name.endswith('_PROTOCOL')] != ['FD_PROTOCOL']:
        raise SystemExit('Only fd: should be enabled')
    libraries = {path.name: fingerprint(path) for path in sorted((prefix / 'lib').glob('libav*.a'))}
    for name, recorded in libraries.items():
        if fingerprint(ffbuild / name.removesuffix('.a') / name)['sha256'] != recorded['sha256']:
            raise SystemExit('Installed helper archive differs from ffprobe archive: ' + name)
    manifest = json.loads((args.corpus / 'manifest.json').read_text())
    report = dict(profile=args.profile, platform=platform.platform(),
                  python=sys.version.split()[0],
                  compilers={'gcc': version(['gcc', '--version']),
                             'g++': version(['g++', '--version'])},
                  versions={'ffprobe': version([commands['ffprobe'][0], '-version']),
                            'helper': version([commands['mini-media-probe'][0], '--version'])},
                  source_pins=json.loads((ROOT / 'sources.json').read_text()),
                  helper_source_sha256=hashlib.sha256((ROOT / 'src/main.cpp').read_bytes()).hexdigest(),
                  configure=json.loads((ffbuild / 'requested-config.json').read_text()),
                  components=enabled, shared_static_archives=libraries,
                  ffmpeg_make_configuration=(ffbuild / 'ffbuild/config.mak').read_text(),
                  helper_compile_commands=json.loads((build / 'compile_commands.json').read_text()),
                  runtime_dependencies={name: subprocess.check_output(
                      ['readelf', '-d', command[0]], text=True, env=ENV)
                      for name, command in commands.items()},
                  commands=commands, binaries=binaries, corpus=manifest, cases=[])
    for case in manifest['cases']:
        path = args.corpus / case['file']
        if fingerprint(path)['sha256'] != case['sha256']:
            raise SystemExit('Corpus checksum mismatch: ' + str(path))
        row = dict(file=case['file'], expected_codec=case['expected_codec'],
                   expected_seconds=case['expected_seconds'])
        for name, command in commands.items():
            samples = [invoke(command, path, name == 'ffprobe') for _ in range(args.repeats)]
            row[name] = samples[0]
            row[name]['stable'] = all(s['exit'] == samples[0]['exit'] and
                                     s['metadata'] == samples[0]['metadata'] for s in samples)
            row[name]['median_ms'] = statistics.median(s['elapsed_ms'] for s in samples)
        left = row['mini-media-probe']['metadata'] or {}
        right = row['ffprobe']['metadata'] or {}
        row['differences'] = {key: {'helper': left.get(key), 'ffprobe': right.get(key)}
                              for key in FIELDS if left.get(key) != right.get(key)}
        report['cases'].append(row)
    summary = {}
    for name in commands:
        rows = report['cases']
        def meta(row):
            return row[name]['metadata'] or {}
        summary[name] = dict(
            extracted=sum(row[name]['exit'] == 0 and
                          bool(meta(row).get('length_seconds') or meta(row).get('codec')) for row in rows),
            codec_correct=sum(meta(row).get('codec') == row['expected_codec'] for row in rows),
            duration_correct=sum(meta(row).get('length_seconds') == row['expected_seconds']
                                 for row in rows if row['expected_seconds'] is not None),
            duration_cases=sum(row['expected_seconds'] is not None for row in rows),
            requested_tags_recovered=sum(meta(row).get(key) == 'Spike ' + key.title() for row in rows
                                         for key in ('artist', 'album', 'title')),
            stable=all(row[name]['stable'] for row in rows))
    report['summary'] = summary
    report['identical_files'] = sum(not row['differences'] for row in report['cases'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    markdown = ['# Matched ffprobe versus mini-media-probe: ' + args.profile, '',
                'FFmpeg n9.0.1; GCC/G++ 15.3; size optimization, no LTO. '
                'Both executables link the same static libav archives. '
                'Only fd: transport is enabled; both receive the same seekable file on stdin. '
                'Library settings and archive hashes, raw ffprobe JSON, '
                'normalized results and corpus hashes are retained in the JSON report.', '',
                '| Metric | mini-media-probe | ffprobe |', '|---|---:|---:|']
    for label, key in [('Stripped executable bytes', 'bytes'), ('gzip -9 bytes', 'gzip9_bytes')]:
        markdown.append(f'| {label} | {binaries["mini-media-probe"][key]:,} | '
                        f'{binaries["ffprobe"][key]:,} |')
    for label, key in [('Extracted / 30', 'extracted'), ('Correct codecs / 30', 'codec_correct'),
                       ('Correct durations / 29', 'duration_correct'),
                       ('Requested tags recovered / 90', 'requested_tags_recovered')]:
        markdown.append(f'| {label} | {summary["mini-media-probe"][key]} | {summary["ffprobe"][key]} |')
    markdown += ['', f'Identical normalized results: {report["identical_files"]}/30 files.', '',
                 '## Field differences', '', '| File | Field | Helper | ffprobe |', '|---|---|---|---|']
    for row in report['cases']:
        for key, values in row['differences'].items():
            markdown.append(f'| {row["file"]} | {key} | {values["helper"]!r} | {values["ffprobe"]!r} |')
    if report['identical_files'] == len(report['cases']):
        markdown.append('| All 30 files | All six fields | Identical | Identical |')
    markdown += ['', 'Expected durations derive from the generator; raw AVC is excluded. '
                 'Tag scores include containers that did not preserve the requested tags. '
                 'ffprobe raw output is normalized to the documented helper publishing policy. '
                 'These results establish corpus coverage, not broad format correctness. '
                 'This is a Linux native comparison; no matching Windows/macOS pair was measured.', '',
                 'Both programs share system libm, zlib and libc. The helper additionally uses '
                 'libstdc++ and libgcc_s; these shared-runtime package sizes are excluded. '
                 'The helper has custom I/O read/seek budgets that are not replicated by ffprobe. '
                 'This is a metadata/size comparison on trusted fixtures, not an equivalent '
                 'malicious-input containment test.']
    output.with_suffix('.md').write_text('\n'.join(markdown) + '\n')
    print(json.dumps({'summary': summary, 'identical_files': report['identical_files'],
                      'binaries': binaries}, indent=2))


if __name__ == '__main__':
    main()
