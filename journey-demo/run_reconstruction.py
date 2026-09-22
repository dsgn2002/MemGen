"""Run the selected reconstruction on Spark, using only local model inference."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


root = Path.home() / 'travel_journey_map'
run = root / 'runs/2026-09-22-scenes-123'
scripts = root / 'scripts'
wheel = root / 'packages/opencv_python_headless-4.13.0.92-cp37-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl'
env = os.environ.copy()
for key in ['STEP_API_KEY', 'STEPFUN_API_KEY', 'OPENAI_API_KEY']:
    env.pop(key, None)
env.update(OMNI_KIT_ACCEPT_EULA='yes', VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/nvidia_icd.json',
           HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONUNBUFFERED='1')


def execute(args):
    subprocess.run([sys.executable, *args], env=env, check=True)


try:
    deadline = time.monotonic() + 900
    while not wheel.exists() and time.monotonic() < deadline:
        time.sleep(5)
    if not wheel.exists():
        raise TimeoutError('OpenCV download has not completed')
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != '5c8cfc8e87ed452b5cecb9419473ee5560a989859fe1d10d1ce11ae87b09a2cb':
        raise ValueError('OpenCV checksum mismatch')
    execute(['-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)])
    execute(['-c', 'import cv2, torch; from moge.model.v2 import MoGeModel; print("DEPENDENCIES_READY", cv2.__version__, torch.cuda.is_available())'])
    execute([str(scripts / 'reconstruct_selected.py'), '--run', str(run),
        '--video', str(root / 'runs/2026-09-22-demo/input/source.mp4'),
        '--checkpoint', str(root / 'models/moge2-small/model.pt'),
        '--checkpoint-sha256', '79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc'])
    execute([str(scripts / 'build_reconstruction.py'), '--run', str(run)])
except Exception as error:
    (run / 'status.json').write_text(json.dumps({'phase': 'failed', 'error': str(error), 'stepfun_calls': 0}, indent=2))
    raise
