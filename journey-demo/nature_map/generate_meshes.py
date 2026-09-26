"""Run TRELLIS.2 on approved local styled images, with Spark-compatible attention."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path('/home/Developer/travel_journey_map')
RUN = ROOT / 'runs/2026-09-26-sai-kung-map'
REPO = ROOT / 'vendor/trellis2-src'
os.environ.update(ATTN_BACKEND='sdpa', SPARSE_ATTN_BACKEND='sdpa',
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
sys.path.insert(0, str(REPO))


def prepare_attention():
    """Use the same attention operation through torch SDPA for variable lengths."""
    path = REPO / 'trellis2/modules/sparse/config.py'
    source = path.read_text()
    source = source.replace("['xformers', 'flash_attn', 'flash_attn_3']", "['xformers', 'flash_attn', 'flash_attn_3', 'sdpa']")
    path.write_text(source)
    path = REPO / 'trellis2/modules/sparse/attention/full_attn.py'
    source = path.read_text()
    if "if config.ATTN == 'sdpa':" not in source:
        source = source.replace("    if config.ATTN == 'xformers':", """    if config.ATTN == 'sdpa':
        if num_all_args == 1:
            q, k, v = qkv.unbind(dim=1)
        elif num_all_args == 2:
            k, v = kv.unbind(dim=1)
        parts = []
        qo = ko = 0
        for qn, kn in zip(q_seqlen, kv_seqlen):
            result = torch.nn.functional.scaled_dot_product_attention(
                q[qo:qo+qn].transpose(0, 1).unsqueeze(0),
                k[ko:ko+kn].transpose(0, 1).unsqueeze(0),
                v[ko:ko+kn].transpose(0, 1).unsqueeze(0))
            parts.append(result.squeeze(0).transpose(0, 1))
            qo += qn
            ko += kn
        out = torch.cat(parts, dim=0)
    elif config.ATTN == 'xformers':""")
        path.write_text(source)


def main():
    global RUN
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--assets", nargs="+", default=["coast", "traveler", "boat"])
    parser.add_argument("--triangles", type=int, default=120000)
    parser.add_argument("--texture-size", type=int, default=2048)
    options = parser.parse_args()
    RUN = options.run
    (RUN / "analysis").mkdir(parents=True, exist_ok=True)
    prepare_attention()
    import numpy as np
    import torch
    from scipy import ndimage
    from PIL import Image
    from trellis2.pipelines import Trellis2ImageTo3DPipeline, rembg
    from trellis2.modules import image_feature_extractor
    import o_voxel

    def extract_dino_features(self, image):
        # Transformers 5 moved the layer stack into an encoder named `model`.
        image = image.to(self.model.embeddings.patch_embeddings.weight.dtype)
        hidden = self.model.embeddings(image, bool_masked_pos=None)
        positions = self.model.rope_embeddings(image)
        if hasattr(self.model, 'model'):
            hidden = self.model.model(hidden, position_embeddings=positions).last_hidden_state
        else:
            for layer in self.model.layer:
                hidden = layer(hidden, position_embeddings=positions)
        return torch.nn.functional.layer_norm(hidden, hidden.shape[-1:])

    image_feature_extractor.DinoV3FeatureExtractor.extract_features = extract_dino_features

    class WhiteBackground:
        """Remove only pale pixels connected to the border of white studio images."""
        def __init__(self, **kwargs):
            pass
        def to(self, *args):
            return self
        def cpu(self):
            return self
        def __call__(self, image):
            rgb = np.asarray(image.convert('RGB'))
            pale = (rgb.min(axis=2) > 225) & (np.ptp(rgb.astype(int), axis=2) < 24)
            edge = np.zeros(pale.shape, dtype=bool)
            edge[[0, -1], :] = pale[[0, -1], :]
            edge[:, [0, -1]] = pale[:, [0, -1]]
            background = ndimage.binary_propagation(edge, mask=pale)
            rgba = np.dstack([rgb, (~background * 255).astype(np.uint8)])
            return Image.fromarray(rgba)

    rembg.WhiteBackground = WhiteBackground
    checkpoint = ROOT / 'models/trellis2-4b'
    config = json.loads((checkpoint / 'pipeline.json').read_text())
    args = config['args']
    args['models']['sparse_structure_decoder'] = str(ROOT / 'models/trellis-sparse/ckpts/ss_dec_conv3d_16l8_fp16')
    args['image_cond_model']['args']['model_name'] = str(ROOT / 'models/dinov3-vitl16')
    args['rembg_model'] = {'name': 'WhiteBackground', 'args': {}}
    args['low_vram'] = True
    args['default_pipeline_type'] = '512'
    (checkpoint / 'pipeline.spark.json').write_text(json.dumps(config, indent=2))
    print('Loading TRELLIS from verified local weights', flush=True)
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(checkpoint), config_file='pipeline.spark.json')
    pipeline.cuda()
    for name in options.assets:
        path = RUN / f'output/{name}.glb'
        if path.exists():
            print('Already generated', name, flush=True)
            continue
        image_path = RUN / f'output/{name}-style.png'
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        image = Image.open(image_path).convert('RGB')
        start = time.monotonic()
        print('GENERATE', name, flush=True)
        mesh = pipeline.run(image, seed=42, pipeline_type='512')[0]
        # Preserve raw inferred geometry before texture baking.
        np.savez_compressed(RUN / f'output/{name}-mesh.npz', vertices=mesh.vertices.cpu().numpy(), faces=mesh.faces.cpu().numpy())
        print('BAKE', name, len(mesh.vertices), len(mesh.faces), flush=True)
        glb = o_voxel.postprocess.to_glb(vertices=mesh.vertices, faces=mesh.faces,
            attr_volume=mesh.attrs, coords=mesh.coords, attr_layout=mesh.layout,
            voxel_size=mesh.voxel_size, aabb=[[-.5, -.5, -.5], [.5, .5, .5]],
            decimation_target=options.triangles, texture_size=options.texture_size, remesh=True,
            remesh_band=1, remesh_project=0, verbose=True)
        glb.export(str(path))
        record = {'model': 'microsoft/TRELLIS.2-4B', 'pipeline': '512',
            'source_image': image_path.name, 'seconds': time.monotonic() - start,
            'original_vertices': len(mesh.vertices), 'original_faces': len(mesh.faces),
            'bytes': path.stat().st_size, 'attention': 'PyTorch SDPA',
            'background_removal': 'border-connected white studio background'}
        (RUN / f'analysis/{name}-3d.json').write_text(json.dumps(record, indent=2))
        print('MESH_COMPLETE', name, flush=True)
        del mesh, glb
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
