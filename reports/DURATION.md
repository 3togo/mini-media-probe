# MP3 duration correction and raw AVC limits

The no-Xing fixture contains 2356 complete MPEG-1 Layer III frames at 44.1 kHz.
Each frame represents 1152 encoded samples: 61.54449 seconds in total, which
rounds to the expected 62 seconds. A sampled bitrate gave 60 seconds. The helper
now counts the complete frame sequence when libav reports bitrate-estimated MP3
duration. It leaves reliable header-derived duration on the original fast path.

Only framing is validated, not decoded audio payloads or CRCs. The scanner checks
MPEG-1/2/2.5 Layer III header length, rejects free-format and reserved headers,
requires contiguous packet positions and complete packet lengths, and accepts a
total only after EOF. A final ID3v1 footer is accepted. Other trailing data,
truncated packets or resynchronisation gaps make the result unknown. Codec and
text tags survive a failed optional duration scan. The scan is limited to files
at most 512 MiB and shares the existing read, seek, time and allocation limits.

Frame counts establish encoded audio duration. Without gapless delay/padding
metadata they do not establish the original trimmed programme duration to the
sample. The 61.5-second generator source and 61.54449-second encoded stream round
to the same integer here; that need not hold for every rounding boundary.

## Corpus and size

Both broad and common profiles now have 30/30 correct codecs, 29/29 correct known
durations and the original 64/90 requested tags. Unchanged minimal ffprobe retains
28/29 known durations. The only differing file is `20-vbr-noxing.mp3`, in duration
and derived bitrate. Raw H.264 is still excluded from the known-duration score.

- [Broad comparison](duration-fix-broad.md), [raw results](duration-fix-broad.json)
- [Common comparison](duration-fix-common.md), [raw results](duration-fix-common.json)

On this toolchain the extra code fits inside the existing executable alignment:
the stripped broad/common helpers remain 2,548,072/1,855,848 bytes. gzip sizes
increase by less than 1 KiB. The previous matched comparison reports are retained
unchanged as historical evidence; each JSON report records the helper source hash.

## Scan cost

Seven warm-cache subprocess measurements on synthetic no-Xing MP3s, including
startup and reading/parsing. See [measurements](duration-scan-cost.json).

| Input | Bytes | Previous median | Full-scan median | Duration before → after |
|---|---:|---:|---:|---:|
| 61.5-second source | 284,091 | 3.63 ms | 6.49 ms | 60 → 62 s |
| 30-minute source | 8,281,673 | 3.62 ms | 89.99 ms | 1748 → 1800 s |

The new path reads the complete audio, so its work grows with file size. These
synthetic local warm-cache results do not establish performance on network
shares or all real music files. Peak memory/CPU profiling was not performed.

## Why raw H.264 is different

FFmpeg's raw-video demuxer supplies a default frame rate of 25 fps, while its
H.264 parser can expose a nominal VUI rate. Neither alone proves a complete
presentation timeline. For the original constant-rate fixture, summing packet
durations happens to produce 10 seconds. Applying that rule generally is unsafe.

A generated ten-second, 30-fps source is reduced to pictures 0,7,...294 while
preserving their timestamps. Matroska carries a 9.833-second timeline. Remuxing
those same pictures to raw Annex B removes their container timestamps; summing
43 nominal packet durations gives only 1.433 seconds. The regression verifies
that the timed container reports 10 rounded seconds while the raw stream remains
unknown. The exact generation commands live in `tests/test_duration.py`; the [timing evidence](raw-h264-timing.json) retains packet positions and timestamps.

Raw AVC duration work is deferred. Missing timing information cannot be
reconstructed reliably by counting pictures or increasing probe size. This change
does not publish an assumed raw-AVC duration.

## Validation

Nine generated-media duration test methods cover the original no-Xing defect,
Xing control, cover art, all nine Layer III sample rates, ID3v1, truncation,
resynchronisation, trailing junk, the scan size limit, raw CFR/VFR timing and a
timed-container control. The no-Xing and damage regressions fail against the
previous executable. Both profiles pass the helper, normalization and duration
CTest groups. AddressSanitizer/UndefinedBehaviorSanitizer checks of the helper
also pass; the prebuilt FFmpeg archives themselves were not sanitizer-instrumented.
The MinGW Windows cross-build succeeds. Native Windows/macOS runtime validation
of this change has not been performed.
