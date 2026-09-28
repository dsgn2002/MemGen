"""Duration regression: ten-minute exports can contain a partial final frame."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trip_upload.media import inspect_upload

class DurationTests(unittest.TestCase):
    def inspect(self, duration):
        with tempfile.TemporaryDirectory() as folder:
            def run(args, **kwargs):
                if args[0] == 'ffprobe':
                    return SimpleNamespace(returncode=0, stdout=json.dumps({
                        'format': {'format_name': 'mov,mp4', 'duration': str(duration)},
                        'streams': [{'codec_type': 'video', 'width': 640, 'height': 360, 'index': 0}]}))
                Path(args[-1]).write_bytes(b'preview fixture')
                return SimpleNamespace(returncode=0)
            with patch('trip_upload.media.subprocess.run', side_effect=run):
                return inspect_upload('fixture.mp4', 'video', folder)

    def test_ten_minute_export_preserves_actual_duration(self):
        for duration in (300, 300.033067, 360, 420, 600, 600.033067, 600.1):
            with self.subTest(duration=duration):
                self.assertEqual(self.inspect(duration)['duration_seconds'], duration)

    def test_rejects_over_limit_and_invalid_durations(self):
        for duration in (600.101, 601, 0, -1, float('nan'), float('inf')):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.inspect(duration)

if __name__ == '__main__':
    unittest.main()
