# mini-media-probe

[![Build and test](https://github.com/3togo/mini-media-probe/actions/workflows/build.yml/badge.svg)](https://github.com/3togo/mini-media-probe/actions/workflows/build.yml)

A standalone C++17 subprocess for extracting duration, overall bitrate, codec,
artist, album and title from an inherited, seekable regular file. It links a
metadata-only FFmpeg build; it does not invoke `ffprobe`, link MediaInfo, or depend
on aMule or wxWidgets.

This independent project is a prototype. It has not been integrated into aMule.
The default output preserves aMule's `AMMP 1` helper protocol; `--json`
provides a general-purpose interface.

## Measured result

### Duration correction

The helper now replaces bitrate-estimated MP3 duration with a bounded full frame
scan. In the existing no-Xing fixture this changes 60 seconds to **62 seconds**,
and overall bitrate from 37 to 36 kbps. The known-duration corpus score becomes
**29/29**, compared with unchanged minimal ffprobe's 28/29. All other corpus
results remain unchanged. [Broad results](reports/duration-fix-broad.md),
[common results](reports/duration-fix-common.md), [method and limitations](reports/DURATION.md).

The scan applies only to raw MP3 whose duration libav estimated from bitrate.
Reliable Xing/VBRI duration remains on the fast path. It requires contiguous,
complete Layer III frames through EOF; an ID3v1 footer is allowed. Files over
512 MiB, truncation, resynchronisation gaps, unsupported/free-format frames or
unknown trailing data leave duration and derived bitrate unknown while keeping
usable codec/tags. Existing time, memory, read and seek bounds remain in force.
This measures encoded frame duration; missing encoder-delay/padding information
still prevents a guarantee of sample-accurate gapless programme duration.

Raw H.264 remains unknown. A checked VFR example retains a 9.833-second timeline
in Matroska, but the same pictures in raw Annex B yield only 1.433 seconds when
nominal packet durations are summed. A full picture count is insufficient when
the original presentation timestamps have been lost.

### Matched ffprobe comparison before the duration correction

Built FFmpeg 9.0.1 with GCC/G++ 15.3, size optimization, no LTO, and no enabled
decoders, encoders, muxers, filters or networking. Within each profile, ffprobe and
the helper link **identical static libav archives**. Only `fd:` transport is
enabled, and both read the same seekable regular file inherited on stdin.

| Linux x86-64 profile | Helper stripped | ffprobe stripped | Helper gzip -9 | ffprobe gzip -9 |
|---|---:|---:|---:|---:|
| Broad: 355 demuxers, 67 parsers | 2,548,072 | 2,707,768 | 1,175,286 | 1,243,985 |
| Common: 24 demuxers, 67 parsers | 1,855,848 | 2,015,544 | 851,618 | 919,174 |

The helper saves 159,696 bytes in either profile: 5.9% of broad ffprobe or 7.9%
of common ffprobe. Both produce identical normalized results for all six fields
on all 30 files: 30 correct codecs, 28/29 correct rounded durations, and 64/90
requested tags recovered. Both estimate the no-Xing MP3 at 60 rather than 62
seconds. Raw H.264 duration remains unknown and is excluded from that score.

ffprobe JSON is normalized using the helper's documented stream/tag selection
policy. The raw JSON is retained for inspection. File sizes exclude shared
runtime dependencies: the helper additionally uses libstdc++ and libgcc_s.
This is a native Linux comparison, not a matching Windows/macOS benchmark.

- [Broad report](reports/ffprobe-broad.md) and [raw data/build evidence](reports/ffprobe-broad.json)
- [Common report](reports/ffprobe-common.md) and [raw data/build evidence](reports/ffprobe-common.json)

Reproduce using the existing generated corpus:

```sh
python3 scripts/build.py --profile broad --with-ffprobe
python3 scripts/build.py --profile common --with-ffprobe
python3 benchmarks/compare_ffprobe.py --profile broad
python3 benchmarks/compare_ffprobe.py --profile common
```

The matched builds use separate `*-matched` build/prefix directories and preserve
the original builds. Checksums verify the existing corpus has not changed.
The comparison tool requires Linux `readelf` and `strip` in addition to the build
requirements below. This benchmark does not compare malicious-input containment:
the helper's custom I/O budgets are not replicated by ffprobe.

### Original MediaInfo comparison

Regenerated the existing 30-file corpus from the [#1904 review](https://github.com/amule-org/amule/pull/1904#issuecomment-6188072318).
Both dependencies and helpers use size-optimized builds, without LTO or source
patches. These numbers are **not** measurements of the existing release packages.

| Linux x86-64 | libav common | libav broad | MediaInfo reference |
|---|---:|---:|---:|
| Stripped helper | 1,851,752 bytes | 2,548,072 bytes | 7,059,760 bytes |
| gzip -9 | 850,159 bytes | 1,173,813 bytes | 2,858,446 bytes |
| Files returning metadata | 30/30 | 30/30 | 30/30 |
| Correct selected codec | 30/30 | 30/30 | 30/30 |
| Correct rounded duration | 28/29 | 28/29 | 29/29 |
| Requested tags recovered | 64/90 | 64/90 | 73/90 |

The common build is 73.8% smaller uncompressed and 70.3% smaller compressed than
the optimized reference. Linux helpers statically link their parser libraries
but share ordinary system runtime libraries and zlib. Library archives are build
inputs and are not shipped alongside these helpers.

The Windows x86-64 broad helper is 3,339,776 bytes stripped (1,464,795 bytes gzip).
It statically links FFmpeg, zlib and the C++ runtime, importing only `bcrypt.dll`,
`KERNEL32.dll` and `msvcrt.dll`. Its results match Linux across all six fields on
the 30 files under Wine. That is not native Windows validation. No Windows
MediaInfo binary was measured, so its size must not be compared directly with the
Linux baseline as a platform-controlled experiment.

Full per-field results, source/corpus hashes and generator commands:

- [Linux broad](reports/linux-broad.md) and [JSON](reports/linux-broad.json)
- [Linux common](reports/linux-common.md) and [JSON](reports/linux-common.json)
- [Windows under Wine](reports/windows-wine.md) and [JSON](reports/windows-wine.json)
- [Method and validation](reports/VALIDATION.md)

MediaInfo still wins this corpus on metadata coverage. The no-Xing VBR MP3 is
estimated at 60 rather than 62 seconds by libav. The nine missing text fields are
AVI album (three files), Theora/Ogg stream tags (three fields), and 3GP tags (three
fields). Some of these are API/policy gaps rather than missing demuxers. Bitrate
accounting also differs. Raw H.264 intentionally remains unknown duration in both
helpers and is excluded from the duration score. The 90-tag denominator includes
containers which did not retain the requested tags; it is not 90 independently
verified tags present in the files.

## Build

Requirements: Python 3.12+, `gh`, CMake 3.20+, Ninja, pkg-config, make, bash,
a C17/C++17 toolchain, and zlib development files. Downloads use `gh` directly,
without inherited proxy settings, and are checked against `sources.json`.
No dependencies are installed globally by the build script.

```sh
python3 scripts/build.py --profile common
ctest --test-dir build-native-common --output-on-failure
```

On Linux, the corresponding tool packages include `build-essential`,
`python3`, `gh`, `cmake`, `ninja-build`, `pkg-config` and `zlib1g-dev`.
On macOS use Xcode command-line tools plus Python, gh, CMake, Ninja and pkg-config.
On Windows run in MSYS2 MINGW64 with the packages shown in
[the native CI workflow](.github/workflows/build.yml).

Profiles:

- `broad` (default): all 355 available demuxers and all 67 parsers in this pin.
- `common`: 24 demuxers covering the corpus and selected adjacent formats, with
  all parsers retained. The MPEG video demuxer is essential for identifying video
  inside MPEG program streams, even though it is not the top-level container.

Both profiles disable every decoder, encoder, muxer, filter, device, protocol and
network transport, along with optional autodetected libraries. Parsing can still
reuse internal codec routines; "no enabled decoders" does not mean libavcodec is
absent. Only libavformat, libavcodec and libavutil are built. zlib is enabled for
compressed container metadata.

Linux-to-Windows cross-build (requires MinGW C and C++ compilers plus zlib):

```sh
python3 scripts/build.py --target windows --profile broad
```

`--cxx /absolute/path/to/compiler` can override the helper's C++ compiler.
Native Linux x86-64, Windows x86-64 and macOS ARM64 builds and all nine helper tests
pass in [GitHub Actions](https://github.com/3togo/mini-media-probe/actions/runs/41808794874).
The workflow uploads each platform's executable, build configuration and license
notices. Linux-to-Windows cross-compilation has also been exercised locally.
GitHub artifact downloads do not preserve executable permissions; restore them
with `chmod +x` on Linux/macOS. Native CI validates the helper tests, while the
30-file metadata comparison above was run locally on Linux and under Wine.

For an existing FFmpeg installation, use CMake directly with its pkg-config path.
The `PROBE_STATIC_FFMPEG` option controls private dependency resolution; the build
script supplies static-only FFmpeg archives. CMake alone may select shared
libraries if the supplied installation contains them.

## Use

In bash or an MSYS2 shell:

```sh
build-native-common/mini-media-probe --json < 'movie.mkv'
```

Portable Python invocation, including Windows:

```python
import subprocess
with open('movie.mkv', 'rb') as source:
    result = subprocess.run(['mini-media-probe', '--json'], stdin=source,
                            capture_output=True, timeout=30)
```

The input must be a regular, seekable file. Its pathname never reaches FFmpeg.
The process reads through a custom AVIO context. External opens are rejected,
including playlists and external track references. Custom AVIO works without
enabling FFmpeg's `file:` or `fd:` protocols.

JSON uses `length_seconds` (nearest integer), `bitrate_kbps` (overall bits/sec
divided by 1000, truncated), `codec`, `artist`, `album`, `title` and `backend`.
Unknown numeric fields are zero, text fields are empty. Codec selection prefers
the first non-cover-art video, otherwise the first audio. Container tags win;
stream-tag fallback is restricted to Vorbis, Opus, FLAC and Speex to preserve the
original aMule policy. This deliberately does not silently broaden metadata
semantics during a parser comparison.

Exit statuses: `0` useful metadata; `10` no usable metadata; `11` parser rejection
or exhausted I/O budget; `12` invocation, input-handle, allocation or I/O failure;
`13` cooperative timeout. In flat mode, `AMMP 1` is flushed before parsing and
success ends with `END`; JSON mode emits only a successful JSON record. The flat
record contains one normalized synthetic stream, matching the existing protocol.

Bounds: 25-second cooperative deadline, 1 GiB cumulative reads, 256 backward or
repeated seeks, 128 MiB per FFmpeg allocation, 5 MiB probing and a 5-second stream
analysis setting. Text is validated as UTF-8 and capped at 4096 bytes per field;
escaping keeps the output below 64 KiB. POSIX adds CPU, address-space, core-dump
and file-size rlimits. These are resource bounds, not an OS sandbox.

**The caller must enforce a hard timeout and kill the process on every platform.**
On Windows, an owning caller should also apply Job-object memory/process limits
and restrict inherited handles, as aMule already does. Cooperative interruption
does not interrupt every possible instruction inside a library parser.

## Reproduce the comparison

```sh
python3 scripts/build.py --profile broad --baseline
python3 scripts/build.py --profile common
python3 benchmarks/generate.py .cache/corpus
mkdir -p .cache/stripped
cp build-native-common/mini-media-probe .cache/stripped/libav-common
cp build-mediainfo/mediainfo-reference .cache/stripped/mediainfo
strip .cache/stripped/libav-common .cache/stripped/mediainfo
python3 benchmarks/compare.py --corpus .cache/corpus \
  --libav .cache/stripped/libav-common --mediainfo .cache/stripped/mediainfo \
  --output reports/linux-common.json
```

Generation needs the FFmpeg encoders listed in the original recipe. It fails
instead of silently skipping an unsupported file. Generator concurrency is
bounded, but the input durations, formats and encoder selections are preserved.
Corpus files are regenerated artifacts rather than the original historical
binary corpus. Three repeats check output stability; this small warm-cache
corpus does not establish performance on large files or network shares.

## License and provenance

Helper and project tooling: GPL-2.0-or-later; see [LICENSE](LICENSE).
The MediaInfo comparison implementation/tests retain their original license and
are copied unchanged, with [source provenance](benchmarks/reference/PROVENANCE.md).
FFmpeg retains its own license. The build copies its LGPL-2.1 text and license
description beside the binary; source versions and archive checksums are pinned.
The default build enables neither GPL nor nonfree FFmpeg components.
