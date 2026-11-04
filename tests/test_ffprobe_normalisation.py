#!/usr/bin/env python3
"""Check ffprobe's adapter against publishing semantics, independent of real corpus results."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
from compare_ffprobe import normalise_ffprobe


class NormalisationTests(unittest.TestCase):
    def test_cover_art_does_not_displace_audio(self):
        raw = {'streams': [dict(index=0, codec_type='video', codec_name='mjpeg',
                                disposition={'attached_pic': 1}),
                           dict(index=1, codec_type='audio', codec_name='mp3')]}
        self.assertEqual(normalise_ffprobe(raw)['codec'], 'mp3')

    def test_first_real_video_wins_in_stream_index_order(self):
        raw = {'streams': [dict(index=4, codec_type='video', codec_name='hevc'),
                           dict(index=0, codec_type='audio', codec_name='aac'),
                           dict(index=2, codec_type='video', codec_name='h264')]}
        self.assertEqual(normalise_ffprobe(raw)['codec'], 'h264')

    def test_numeric_rounding_and_unknowns(self):
        for value, expected in [('2.49', 2), ('2.5', 3), ('N/A', 0), ('NaN', 0),
                                ('Infinity', 0), ('-1', 0), ('999999999999', 4294967295)]:
            with self.subTest(value=value):
                result = normalise_ffprobe({'format': {'duration': value, 'bit_rate': '768999'}})
                self.assertEqual(result['length_seconds'], expected)
                self.assertEqual(result['bitrate_kbps'], 768)

    def test_container_tags_win_and_fallback_is_restricted(self):
        raw = {'format': {'tags': {'ARTIST': 'Container'}},
               'streams': [dict(index=0, codec_type='audio', codec_name='opus',
                                tags={'artist': 'Track artist', 'TITLE': 'Track title'})]}
        self.assertEqual(normalise_ffprobe(raw)['artist'], 'Container')
        self.assertEqual(normalise_ffprobe(raw)['title'], 'Track title')
        raw['streams'][0]['codec_name'] = 'aac'
        self.assertEqual(normalise_ffprobe(raw)['title'], '')


if __name__ == '__main__':
    unittest.main()
