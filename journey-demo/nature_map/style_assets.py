"""Generate reference-conditioned assets from an explicit scene specification."""
import argparse
import json
import os
import time
from pathlib import Path

os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    run = Path(spec['run'])
    (run / 'output').mkdir(parents=True, exist_ok=True)
    (run / 'analysis').mkdir(parents=True, exist_ok=True)
    import torch
    from PIL import Image
    from diffusers import QwenImageEditPlusPipeline
    checkpoint = '/home/Developer/travel_journey_map/models/qwen-image-edit-2511'
    pipe = QwenImageEditPlusPipeline.from_pretrained(checkpoint, torch_dtype=torch.bfloat16, local_files_only=True).to('cuda')
    pipe.vae.enable_tiling()
    for index, item in enumerate(spec['assets']):
        output = run / 'output' / (item['name'] + '-style.png')
        if output.exists():
            continue
        source = Image.open(item['source']).convert('RGB')
        if item.get('crop'):
            source = source.crop(item['crop'])
        source.thumbnail((640, 640))
        start = time.monotonic()
        seed = item.get('seed', 320 + index)
        print('STYLING', item['name'], flush=True)
        with torch.inference_mode():
            result = pipe(image=[source], prompt=item['prompt'], negative_prompt=' ', width=640, height=640,
                          num_inference_steps=24, true_cfg_scale=4.0,
                          generator=torch.Generator(device='cuda').manual_seed(seed)).images[0]
        result.save(output)
        (run / 'analysis' / (item['name'] + '-style.json')).write_text(json.dumps({**item, 'model':checkpoint,
            'seconds':time.monotonic()-start, 'seed':seed, 'steps':24}, indent=2))
        print('STYLE_COMPLETE', item['name'], flush=True)

if __name__ == '__main__':
    main()
