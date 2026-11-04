#!/usr/bin/env python3
"""Portable tests through the real inherited-file interface."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

HELPER = str(Path(sys.argv.pop(1)).resolve())
COMMAND = ([os.environ['PROBE_RUNNER']] if os.environ.get('PROBE_RUNNER') else []) + [HELPER]


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / '媒体 with spaces.wav'
        self.wav(144000)

    def tearDown(self):
        self.tmp.cleanup()

    def wav(self, frames, width=2, rate=48000):
        with wave.open(str(self.path), 'wb') as out:
            out.setparams((1, width, rate, 0, 'NONE', 'not compressed'))
            out.writeframes(bytes(frames * width))

    def probe(self, args=('--json',)):
        with self.path.open('rb') as source:
            return subprocess.run([*COMMAND, *args], stdin=source, capture_output=True, timeout=30)

    def title(self, text):
        def syncsafe(n):
            return bytes((n >> 21 & 127, n >> 14 & 127, n >> 7 & 127, n & 127))
        value = b'\x03' + text
        frame = b'TIT2' + syncsafe(len(value)) + b'\0\0' + value
        tag = b'ID3\x04\0\0' + syncsafe(len(frame)) + frame
        chunk = b'id3 ' + struct.pack('<I', len(tag)) + tag + b'\0' * (len(tag) % 2)
        data = bytearray(self.path.read_bytes() + chunk)
        struct.pack_into('<I', data, 4, len(data) - 8)
        self.path.write_bytes(data)

    def test_wav(self):
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['length_seconds'], 3)
        self.assertEqual(data['codec'], 'pcm_s16le')
        self.assertEqual(data['bitrate_kbps'], 768)

    def test_rounding(self):
        for frames, seconds in [(119520, 2), (120000, 3), (124800, 3)]:
            with self.subTest(frames=frames):
                self.wav(frames)
                self.assertEqual(json.loads(self.probe().stdout)['length_seconds'], seconds)

    def test_codec_only(self):
        self.wav(800, 1, 8000)
        data = json.loads(self.probe().stdout)
        self.assertEqual(data['length_seconds'], 0)
        self.assertEqual(data['codec'], 'pcm_u8')

    def test_unicode_and_escaping(self):
        title = '艺术家 🎵 "quoted" \\ path\nline\ttab'
        self.title(title.encode())
        self.assertEqual(json.loads(self.probe().stdout)['title'], title)
        lines = self.probe(()).stdout.decode('utf-8').splitlines()
        self.assertEqual(len(lines), 9)
        self.assertEqual((lines[0], lines[-1]), ('AMMP 1', 'END'))

    def test_oversized_tag(self):
        self.title(('🎵' * 20000).encode())
        result = self.probe()
        self.assertEqual(result.returncode, 0)
        self.assertLess(len(result.stdout), 64 * 1024)
        self.assertLessEqual(len(json.loads(result.stdout)['title'].encode()), 4096)

    def test_malformed_and_empty(self):
        for content in [b'', b'not media', b'RIFF\xff\xff\xff\xffWAVEfmt ']:
            with self.subTest(content=content):
                self.path.write_bytes(content)
                result = self.probe(())
                self.assertIn(result.returncode, (10, 11))
                self.assertEqual(result.stdout, b'AMMP 1\n')

    def test_no_new_files_from_playlist(self):
        secret = Path(self.tmp.name) / 'external.wav'
        self.path.rename(secret)
        self.path.write_text(f'ffconcat version 1.0\nfile {secret.as_posix()}\n')
        result = self.probe()
        self.assertIn(result.returncode, (10, 11))
        self.assertEqual(result.stdout, b'')

    def test_nonseekable_stdin(self):
        result = subprocess.run(COMMAND, input=b'RIFF', capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 12)
        self.assertEqual(result.stdout, b'')

    def test_bad_option(self):
        self.assertEqual(self.probe(('--unknown',)).returncode, 12)


if __name__ == '__main__':
    unittest.main()
