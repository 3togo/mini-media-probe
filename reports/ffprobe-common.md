# Matched ffprobe versus mini-media-probe: common

FFmpeg n9.0.1; GCC/G++ 15.3; size optimization, no LTO. Both executables link the same static libav archives. Only fd: transport is enabled; both receive the same seekable file on stdin. Library settings and archive hashes, raw ffprobe JSON, normalized results and corpus hashes are retained in the JSON report.

| Metric | mini-media-probe | ffprobe |
|---|---:|---:|
| Stripped executable bytes | 1,855,848 | 2,015,544 |
| gzip -9 bytes | 851,618 | 919,174 |
| Extracted / 30 | 30 | 30 |
| Correct codecs / 30 | 30 | 30 |
| Correct durations / 29 | 28 | 28 |
| Requested tags recovered / 90 | 64 | 64 |

Identical normalized results: 30/30 files.

## Field differences

| File | Field | Helper | ffprobe |
|---|---|---|---|
| All 30 files | All six fields | Identical | Identical |

Expected durations derive from the generator; raw AVC is excluded. Tag scores include containers that did not preserve the requested tags. ffprobe raw output is normalized to the documented helper publishing policy. These results establish corpus coverage, not broad format correctness. This is a Linux native comparison; no matching Windows/macOS pair was measured.

Both programs share system libm, zlib and libc. The helper additionally uses libstdc++ and libgcc_s; these shared-runtime package sizes are excluded. The helper has custom I/O read/seek budgets that are not replicated by ffprobe. This is a metadata/size comparison on trusted fixtures, not an equivalent malicious-input containment test.
