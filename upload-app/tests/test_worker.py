"""Process safety checks using owned CPU subprocesses, never the GPU model."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trip_upload.worker import stop_child


class WorkerTests(unittest.TestCase):
    def test_cancel_stops_only_owned_process_group(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            stop_child(child)
            self.assertIsNotNone(child.poll())
            self.assertIsNone(unrelated.poll())
            stop_child(child)  # Already exited is safe.
        finally:
            stop_child(child)
            stop_child(unrelated)

    def test_second_worker_cannot_enter_locked_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            with (Path(directory) / 'worker.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'manage.py'),
                                         'worker', '--once'], env={**os.environ, 'TRIP_DATA':directory},
                                        capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('already owns this queue', result.stderr)


if __name__ == '__main__':
    unittest.main()
