#!/usr/bin/env python3
"""Compare all six published fields, preserving failures and every difference."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

FIELDS = ['length_seconds', 'bitrate_kbps', 'codec', 'artist', 'album', 'title']
TAGS = dict(artist='Spike Artist', album='Spike Album', title='Spike Title')
ENV = {k: v for k, v in os.environ.items()
       if k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy', 'ld_preload')}


def invoke(command, path):
    start = time.monotonic()
    with path.open('rb') as source:
        try:
            result = subprocess.run([*command, '--json'], stdin=source,
                                    capture_output=True, timeout=30, env=ENV)
        except subprocess.TimeoutExpired:
            return dict(exit='timeout', metadata=None, elapsed_ms=30000)
    metadata = None
    error = result.stderr.decode(errors='replace')
    if result.returncode == 0:
        try:
            metadata = json.loads(result.stdout)
        except (ValueError, UnicodeError) as exc:
            error += str(exc)
    return dict(exit=result.returncode, metadata=metadata, stderr=error,
                elapsed_ms=(time.monotonic() - start) * 1000)


def size(path):
    data = path.read_bytes()
    return dict(bytes=len(data), gzip9_bytes=len(gzip.compress(data, compresslevel=9, mtime=0)),
                sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--libav', type=Path, required=True)
    parser.add_argument('--mediainfo', type=Path, required=True)
    parser.add_argument('--runner', help='Optional executable runner, e.g. wine, for libav only')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    manifest = json.loads((args.corpus / 'manifest.json').read_text())
    commands = dict(libav=([args.runner] if args.runner else []) + [str(args.libav.resolve())],
                    mediainfo=[str(args.mediainfo.resolve())])
    report = dict(platform=platform.platform(), manifest=manifest,
                  libav_runner=args.runner,
                  binaries={name: size(path) for name, path in
                            [('libav', args.libav), ('mediainfo', args.mediainfo)]}, cases=[])
    for case in manifest['cases']:
        path = args.corpus / case['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != case['sha256']:
            raise SystemExit(f'Corpus checksum mismatch: {path}')
        row = dict(file=case['file'], expected_codec=case['expected_codec'],
                   expected_seconds=case['expected_seconds'])
        for name, command in commands.items():
            samples = [invoke(command, path) for _ in range(args.repeats)]
            row[name] = samples[0]
            row[name]['median_ms'] = statistics.median(s['elapsed_ms'] for s in samples)
            row[name]['stable'] = all(s['exit'] == samples[0]['exit'] and
                                      s['metadata'] == samples[0]['metadata'] for s in samples)
        left = row['libav']['metadata'] or {}
        right = row['mediainfo']['metadata'] or {}
        row['differences'] = {field: dict(libav=left.get(field), mediainfo=right.get(field))
                              for field in FIELDS if left.get(field) != right.get(field)}
        report['cases'].append(row)
    summary = {}
    for name in commands:
        rows = report['cases']
        def meta(row):
            return row[name]['metadata'] or {}
        summary[name] = dict(
            extracted=sum(row[name]['exit'] == 0 and row[name]['metadata'] is not None for row in rows),
            codec_correct=sum(meta(row).get('codec') == row['expected_codec'] for row in rows),
            duration_correct=sum(meta(row).get('length_seconds') == row['expected_seconds']
                                 for row in rows if row['expected_seconds'] is not None),
            duration_cases=sum(row['expected_seconds'] is not None for row in rows),
            requested_tags_recovered=sum(meta(row).get(key) == value for row in rows
                                         for key, value in TAGS.items()),
            stable=all(row[name]['stable'] for row in rows),
            corpus_median_ms_total=sum(row[name]['median_ms'] for row in rows))
    report['summary'] = summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    markdown = ['# Metadata and size comparison', '',
                'Regenerated existing 30-file corpus. Expected durations derive from generator inputs; '
                'raw AVC is excluded from the duration score. Requested-tag score is out of 90, '
                'including containers that did not retain the requested tags. Agreement is not correctness.', '']
    if args.runner:
        markdown += ['The libav binary runs through an executable compatibility runner; '
                     'the MediaInfo reference runs natively on the host. The executable sizes '
                     'are from different target platforms and are not a controlled package-size comparison.', '']
    markdown += ['| Metric | libav | MediaInfo |', '|---|---:|---:|']
    for label, key in [('Extracted files / 30', 'extracted'), ('Correct codecs / 30', 'codec_correct'),
                       ('Correct rounded durations / 29', 'duration_correct'),
                       ('Requested tags recovered / 90', 'requested_tags_recovered')]:
        markdown.append(f'| {label} | {summary["libav"][key]} | {summary["mediainfo"][key]} |')
    for label, key in [('Stripped helper bytes', 'bytes'), ('gzip -9 bytes', 'gzip9_bytes')]:
        markdown.append(f'| {label} | {report["binaries"]["libav"][key]:,} | '
                        f'{report["binaries"]["mediainfo"][key]:,} |')
    markdown += ['', '## Differences', '', '| File | Field | libav | MediaInfo |', '|---|---|---|---|']
    for row in report['cases']:
        for field, values in row['differences'].items():
            markdown.append(f'| {row["file"]} | {field} | {values["libav"]!r} | {values["mediainfo"]!r} |')
    args.output.with_suffix('.md').write_text('\n'.join(markdown) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
