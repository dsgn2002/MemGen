import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'skills' / '_shared'))


@dataclass
class Settings:
    data: Path
    model: str = ''
    worker_python: str = sys.executable
    secure_cookie: bool = True
    coarse: int = 96
    refinement: int = 24
    batch: int = 3
    stage_timeout: int = 7200
    chunk_size: int = 8 * 1024 * 1024
    max_video: int = 500 * 1024 * 1024
    max_photo: int = 20 * 1024 * 1024
    max_projects: int = 10
    generation_root: str = os.environ.get('TRIP_GENERATION_ROOT', '/home/Developer/travel_journey_map')

    @classmethod
    def env(cls):
        return cls(Path(os.environ.get('TRIP_DATA', ROOT.parent / 'tmp' / 'upload-data')).resolve(),
                   os.environ.get('MEMGEN_QWEN_MODEL', ''),
                   os.environ.get('TRIP_WORKER_PYTHON', sys.executable),
                   os.environ.get('TRIP_COOKIE_SECURE', '1') != '0',
                   int(os.environ.get('TRIP_COARSE_BUDGET', '96')),
                   int(os.environ.get('TRIP_REFINEMENT_BUDGET', '24')),
                   int(os.environ.get('TRIP_BATCH_SIZE', '3')))
