"""Create compact browser GLBs while retaining the original editable assets."""
import json
import subprocess
import time
from pathlib import Path
import trimesh

ROOT = Path('/home/Developer/travel_journey_map')
RUN = ROOT / 'runs/2026-09-26-sai-kung-map'
packer = ROOT / 'vendor/meshoptimizer-0.25/gltfpack'
report = {}
for name in ['coast', 'traveler', 'boat']:
    while not (RUN / f'analysis/{name}-3d.json').exists():
        time.sleep(5)
    source = RUN / f'output/{name}.glb'
    temporary = RUN / f'output/{name}.webp.glb'
    target = RUN / f'output/{name}.web.glb'
    mesh = trimesh.load(source, force='scene')
    mesh.export(temporary, file_type='glb', extension_webp=True)
    subprocess.run([str(packer), '-i', str(temporary), '-o', str(target), '-cc'], check=True)
    temporary.unlink()
    report[name] = {'original_bytes': source.stat().st_size, 'browser_bytes': target.stat().st_size}
    print('BROWSER_ASSET', name, report[name], flush=True)
(RUN / 'output/browser-assets.json').write_text(json.dumps(report, indent=2))
