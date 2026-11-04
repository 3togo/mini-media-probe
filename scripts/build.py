#!/usr/bin/env python3
"""Build pinned metadata-only FFmpeg and the standalone helper, without global installs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def direct_environment():
    return {k: v for k, v in os.environ.items()
            if k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy', 'ld_preload')}


def source(name):
    pin = json.loads((ROOT / 'sources.json').read_text())[name]
    cache = ROOT / '.cache' / 'sources'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (name + '.tar.gz')
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        with partial.open('wb') as output:
            subprocess.run(['gh', 'api', f'repos/{pin["repo"]}/tarball/{pin["ref"]}'],
                           stdout=output, env=direct_environment(), check=True)
        partial.replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != pin['sha256']:
        raise SystemExit(f'Checksum mismatch: {archive}')
    target = cache / name
    if not target.exists():
        target.mkdir()
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts[1:]
                if not parts:
                    continue
                member.name = Path(*parts).as_posix()
                tar.extract(member, target, filter='data')
    return target


def run(args, **kwargs):
    command = list(map(str, args))
    # Windows CreateProcess searches system directories before PATH. Resolve explicitly
    # so the MSYS2 bash wins over System32's WSL stub, matching the invoking shell.
    command[0] = shutil.which(command[0], path=kwargs.get('env', os.environ).get('PATH')) or command[0]
    print('+', ' '.join(command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['native', 'windows'], default='native')
    parser.add_argument('--profile', choices=['broad', 'common'], default='broad')
    parser.add_argument('--jobs', type=int, default=min(os.cpu_count() or 2, 12))
    parser.add_argument('--cxx', help='Override the helper C++ compiler')
    parser.add_argument('--baseline', action='store_true', help='Also build static MediaInfo reference')
    args = parser.parse_args()
    env = direct_environment()
    suffix = args.target + '-' + args.profile
    prefix = ROOT / '.cache' / ('prefix-' + suffix)
    ffbuild = ROOT / '.cache' / ('ffmpeg-' + suffix)
    prefix.mkdir(parents=True, exist_ok=True)
    ffbuild.mkdir(exist_ok=True)
    ffsource = source('ffmpeg')
    flags = ['--disable-autodetect', '--disable-everything', '--disable-programs',
             '--disable-doc', '--disable-debug', '--disable-network', '--disable-avdevice',
             '--disable-avfilter', '--disable-swscale', '--disable-swresample',
             '--disable-shared', '--enable-static', '--enable-small', '--enable-zlib',
             '--disable-x86asm', '--enable-pic', '--enable-parsers']
    if args.profile == 'broad':
        flags += ['--enable-demuxers']
    else:
        flags += ['--enable-demuxer=aac,ac3,aiff,amr,ape,asf,avi,dts,eac3,flac,flv,gsm,h264,'
                  'hevc,matroska,mov,mp3,mpegps,mpegts,mpegvideo,ogg,wav,wv,tta']
    toolchain = []
    if args.target == 'windows':
        flags += ['--enable-cross-compile', '--target-os=mingw32', '--arch=x86_64',
                  '--cross-prefix=x86_64-w64-mingw32-']
        toolchain = ['-DCMAKE_SYSTEM_NAME=Windows', '-DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc',
                     '-DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++']
        env['PKG_CONFIG_LIBDIR'] = str(prefix / 'lib/pkgconfig')
    if args.cxx:
        toolchain = [flag for flag in toolchain if not flag.startswith('-DCMAKE_CXX_COMPILER=')]
        toolchain.append('-DCMAKE_CXX_COMPILER=' + args.cxx)
    config = ['bash', (ffsource / 'configure').as_posix(), '--prefix=' + prefix.as_posix(), *flags]
    stamp = ffbuild / 'requested-config.json'
    if not stamp.exists() or json.loads(stamp.read_text()) != config:
        run(config, cwd=ffbuild, env=env)
        stamp.write_text(json.dumps(config, indent=2))
    run(['make', '-j', args.jobs], cwd=ffbuild, env=env)
    run(['make', 'install'], cwd=ffbuild, env=env)
    env['PKG_CONFIG_PATH'] = str(prefix / 'lib/pkgconfig')
    build = ROOT / ('build-' + suffix)
    run(['cmake', '-S', ROOT, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=MinSizeRel',
         '-DPROBE_STATIC_FFMPEG=ON', *toolchain], env=env)
    run(['cmake', '--build', build, '-j', args.jobs], env=env)
    licenses = build / 'licenses/ffmpeg'
    licenses.mkdir(parents=True, exist_ok=True)
    for name in ['COPYING.LGPLv2.1', 'LICENSE.md']:
        shutil.copy2(ffsource / name, licenses)
    (build / 'ffmpeg-configuration.txt').write_text((ffbuild / 'ffbuild/config.mak').read_text())
    if args.baseline:
        if args.target != 'native':
            raise SystemExit('Use native baseline build; cross baseline is not configured')
        build_baseline(args.jobs, env)


def build_baseline(jobs, env):
    prefix = ROOT / '.cache/mediainfo-prefix'
    for name in ['zenlib', 'mediainfo']:
        src = source(name)
        build = ROOT / ('.cache/' + name + '-build')
        run(['cmake', '-S', src / 'Project/CMake', '-B', build, '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=MinSizeRel', '-DCMAKE_CXX_STANDARD=17',
             '-DCMAKE_POLICY_VERSION_MINIMUM=3.10', '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
             '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_INSTALL_LIBDIR=lib',
             '-DBUILD_SHARED_LIBS=OFF', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
             '-DBUILD_ZENLIB=OFF', '-DBUILD_ZLIB=OFF', '-DCMAKE_DISABLE_FIND_PACKAGE_TinyXML=ON',
             '-DCMAKE_DISABLE_FIND_PACKAGE_CURL=ON',
             '-DCMAKE_CXX_FLAGS=-DMEDIAINFO_LIBCURL_NO -DMEDIAINFO_LIBMMS_NO'], env=env)
        run(['cmake', '--build', build, '-j', jobs], env=env)
        run(['cmake', '--install', build], env=env)
    run(['cmake', '-S', ROOT / 'benchmarks/reference', '-B', ROOT / 'build-mediainfo',
         '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=MinSizeRel', '-DMEDIA_PREFIX=' + str(prefix)], env=env)
    run(['cmake', '--build', ROOT / 'build-mediainfo', '-j', jobs], env=env)


if __name__ == '__main__':
    main()
