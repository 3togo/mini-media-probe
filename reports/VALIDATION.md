# Validation, 2026-11-04 UTC

## Native hosted CI

Published as [3togo/mini-media-probe](https://github.com/3togo/mini-media-probe).
[Native CI at `666f87229fb04cff83d86204f2b206e77ca7506e`](https://github.com/3togo/mini-media-probe/actions/runs/41808794874)
passes on Linux x86-64 (Ubuntu 24.04), Windows x86-64 (Windows Server 2022/MSYS2)
and macOS ARM64 (macOS 14). All nine helper tests pass on each platform; all three
jobs upload their executable, source pins, FFmpeg configuration and license notices.
This establishes native helper-test coverage, not a native cross-platform rerun
of the 30-file corpus below. The original Linux and Wine comparison remains valid.

The first Windows run exposed native Python launching the System32 WSL `bash`
stub instead of MSYS2 Bash. Resolving build tools to their full paths with
`shutil.which` fixes that mismatch; native Windows CI verifies the correction.

## Original local comparison

Host: Linux-7.2.6-070206-generic-x86_64-with-glibc2.44

```text
c++ (Ubuntu 15.3.0-4ubuntu1) 15.3.0
cmake version 4.3.4
1.13.2
```

Helper source SHA-256: `c355772858b3cebb69e1118b735316528b697492b48745a05788c55b6e79bd06`. Source/archive pins are in
`../sources.json`; exact fixture bytes, generation commands and hashes are embedded
in every comparison JSON. No source patches or LTO were used for dependencies.

## Builds

- FFmpeg n9.0.1, libavformat/libavcodec/libavutil, static archives; `--enable-small`,
  all decoders/encoders/muxers/filters/protocols/network disabled. Both profiles
  retain all 67 parsers. Broad enables 355 demuxers, common enables 24.
- FFmpeg uses its own size-oriented optimization with `--enable-small`.
  Both helper executables and MediaInfo/ZenLib use CMake `MinSizeRel` (`-Os`).
- MediaInfoLib 26.05 and ZenLib 0.4.41, statically linked, curl/libmms disabled,
  matching aMule's source-build exclusions. zlib remains dynamically linked on
  Linux for both helpers. Ordinary C/C++ runtimes remain dynamic on Linux.
- Linux dependencies: `libm`, `libz`, `libstdc++`, `libgcc_s`, `libc`; no shared
  libav*, MediaInfo or ZenLib dependency. Verified with ELF dynamic entries.
- Windows cross-build: MinGW GCC/G++ 16-win32, x86-64. FFmpeg, zlib and C++ runtime
  statically linked; PE imports only bcrypt.dll, KERNEL32.dll, msvcrt.dll.
  The host lacked G++; its matching package was extracted into the ignored cache,
  with existing compiler support files referenced there. No host packages changed.
- At the time of this local comparison, native hosted CI had not been dispatched.
  Its results are now recorded above. The Windows corpus checks here use Wine.

## Tests

- Linux common and broad: all 9 helper tests pass through inherited regular files.
- Windows broad under Wine: all 9 helper tests pass (87.4 seconds including Wine
  startup across subprocesses).
- clang-format-18 check and clang-tidy-18 analysis of the helper pass.
- Existing unchanged MediaInfo backend suite: 15/15 tests pass on the pinned
  MediaInfo reference. The libav broad helper passes 14/15 test methods; its one
  failing subcase is the AVI album lookup in the additional-container test.
  This is a recorded coverage difference, not a passing parity suite.
  The existing suite includes optional generated codec fixtures; encoders
  unavailable on this host may be skipped by that original suite. The 30-file
  benchmark instead fails generation on any missing required encoder.
- Original 30-file corpus regenerated from the historical recipe, with only
  generator concurrency bounded. All 30 generated successfully.
- Linux broad/common: three runs per file, stable statuses and all six fields.
  Windows broad: one run per file under Wine, identical metadata to Linux.
- Both profiles and the Windows build return metadata for 30/30 files and the
  expected selected codec for 30/30. Neither libav profile reaches MediaInfo's
  text-tag and duration coverage. Every field difference is retained in JSON/MD.

## Interpretation and limits

The optimized MediaInfo reference is 7,059,760 bytes stripped, rather than the
11.8 MB Release measurement in issue #2349. Different optimization/toolchains
matter: do not compare our size-optimized libav build against that external
Release number. The compressed numbers measure gzip of the stripped executable,
not a complete distribution package with notices and ordinary platform runtimes.
Windows sizes include its static C++ runtime and are not directly comparable
with the Linux baseline for deciding a Windows package saving.

Duration expectations use known generator inputs and nearest-second rounding;
raw H.264 has no accepted reliable timeline and is excluded, leaving 29 cases.
The no-Xing MP3 mismatch is visible (60 versus expected 62). Tiny audio streams,
encoder delay and container overhead limit stronger precision conclusions.
Tag scores count exact requested values out of 90, including containers which
cannot preserve them. Bitrate differences are reported without choosing one
library as a correctness oracle. Corpus agreement does not establish general
format correctness, malicious-input safety or production readiness.

Small warm-cache process timings are in JSON for reproducibility only. They are
not representative throughput/CPU/memory measurements. Large files, network
shares, broader hostile/fuzz corpora, native Windows/macOS corpus comparisons,
and application-level integration remain future validation work.

## Reference provenance

MediaInfo reference and backend tests copied unchanged from amule-org/amule commit `8e2afa46b1a73177e6eff3a8a7a4ab6ce91a89ec` (GPL-2.0-or-later).

Corpus recipe: https://github.com/amule-org/amule/pull/1904#issuecomment-6188072318
Regenerated using the host FFmpeg; files are not original binary artifacts.
