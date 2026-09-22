"""Reconstruct selected video moments as animated, textured depth surfaces.

Runs locally on DGX Spark. No StepFun client or paid inference API is used.
This is single-view geometry estimation, not a complete scan of hidden sides.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np
from PIL import Image


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def make_faces(width, height):
    a = np.arange((height - 1) * width).reshape(height - 1, width)[:, :-1].flatten()
    # CV -> OpenGL conversion flips both Y and Z; this winding faces the camera.
    return np.concatenate([np.stack([a, a + width, a + 1], axis=1),
        np.stack([a + 1, a + width, a + width + 1], axis=1)]).astype(np.int32)


def points_from_depth(depth, intrinsics, factor, focus):
    height, width = depth.shape
    u, v = np.meshgrid((np.arange(width) + 0.5) / width,
                       (np.arange(height) + 0.5) / height)
    x = (u - intrinsics[0, 2]) / intrinsics[0, 0] * depth
    y = (v - intrinsics[1, 2]) / intrinsics[1, 1] * depth
    return np.stack([x * factor, -y * factor, (focus - depth) * factor], axis=-1).reshape(-1, 3).astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--model-name', default='Ruicheng/moge-2-vits-normal')
    parser.add_argument('--fps', type=int, default=8)
    parser.add_argument('--seconds', type=float, default=1.5)
    parser.add_argument('--grid-width', type=int, default=240)
    args = parser.parse_args()
    selection = json.loads((args.run / 'input/selection.json').read_text())
    if sha256(args.video) != selection['source']['sha256']:
        raise ValueError('Video differs from the selected source')
    if not args.checkpoint.is_file() or sha256(args.checkpoint) != args.checkpoint_sha256:
        raise ValueError('A locally verified model checkpoint is required')
    selected = selection.get('scenes') or [selection['scene']]
    if not selected or len({scene['id'] for scene in selected}) != len(selected):
        raise ValueError('Select unique scenes before reconstruction')
    output = args.run / 'output'
    output.mkdir(parents=True, exist_ok=True)
    write(args.run / 'status.json', {'phase': 'loading_model', 'stepfun_calls': 0})

    import torch
    from moge.model.v2 import MoGeModel
    if not torch.cuda.is_available():
        raise RuntimeError('This run requires the authorized Spark GPU')
    torch.set_num_threads(6)
    model = MoGeModel.from_pretrained(str(args.checkpoint)).to('cuda').eval()
    started = time.monotonic()
    manifest = {
        'title': 'My Travel Journey', 'source': selection['source'], 'scenes': [],
        'method': 'MoGe-2 estimated geometry; original video textures; Omniverse USD assembly and rendering',
        'model': args.model_name, 'model_sha256': args.checkpoint_sha256,
        'stepfun_calls': 0, 'animation': 'source footage on estimated surfaces, plus camera movement',
        'limitations': [
            'Single-view depth projection; hidden sides and unseen surroundings are not reconstructed.',
            'Nearby viewpoints retain the source appearance; wide rotations expose stretched surfaces.',
            'People retain their recorded motion; they are not separately rigged 3D characters.',
            'Dimensions are normalized for presentation; depth is estimated, not measured.',
        ],
    }
    for scene in selected:
        scene_started = time.monotonic()
        destination = output / scene['id']
        frames = destination / 'frames'
        frames.mkdir(parents=True, exist_ok=True)
        start = float(scene['hero_timestamp_s'])
        end = min(start + args.seconds, scene['clip_range_s'][1])
        duration = end - start
        count = max(1, round(duration * args.fps))
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(start),
            '-i', str(args.video), '-t', str(duration), '-an', '-vf', 'scale=960:-2',
            '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-movflags', '+faststart',
            '-y', str(destination / 'source-motion.mp4')], check=True)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(start),
            '-i', str(args.video), '-t', str(duration), '-vf', f'fps={args.fps},scale=960:-2',
            '-frames:v', str(count), '-start_number', '0', '-q:v', '2', '-y',
            str(frames / 'frame-%03d.jpg')], check=True)
        images = sorted(frames.glob('frame-*.jpg'))[:count]
        maps = []
        intrinsics = None
        fov_x = None
        baseline = None
        width = args.grid_width
        height = round(width * 9 / 16)
        for i, path in enumerate(images):
            image = np.asarray(Image.open(path).convert('RGB'))
            tensor = torch.tensor(image.copy(), device='cuda', dtype=torch.float32).permute(2, 0, 1) / 255
            prediction = model.infer(tensor, resolution_level=4, fov_x=fov_x,
                apply_mask=False, use_fp16=True)
            depth = prediction['depth'].float().cpu().numpy()
            mask = prediction['mask'].cpu().numpy().astype(bool)
            valid = mask & np.isfinite(depth) & (depth > 0)
            if valid.mean() < 0.15:
                raise ValueError(f'Insufficient valid geometry in {scene["id"]}, frame {i}')
            if intrinsics is None:
                intrinsics = prediction['intrinsics'].float().cpu().numpy()
                fov_x = math.degrees(2 * math.atan(0.5 / float(intrinsics[0, 0])))
                baseline = float(np.median(depth[valid]))
            # Stabilize ambiguous monocular scale, preserving per-frame shape changes.
            depth *= baseline / float(np.median(depth[valid]))
            near, far = np.quantile(depth[valid], [0.01, 0.98])
            depth = np.where(valid, np.clip(depth, max(near * 0.5, 0.05), far), far * 1.4)
            small = np.asarray(Image.fromarray(depth.astype(np.float32)).resize((width, height), Image.Resampling.BILINEAR))
            maps.append(small)
            write(args.run / 'status.json', {'phase': 'reconstructing', 'scene': scene['id'],
                'frame': i + 1, 'frames': len(images), 'stepfun_calls': 0})
            print(f'GEOMETRY {scene["id"]} {i + 1}/{len(images)}', flush=True)
        depth_stack = np.stack(maps).astype(np.float32)
        if not np.isfinite(depth_stack).all() or depth_stack.min() <= 0:
            raise ValueError('Reconstruction contains invalid depth')
        focus = float(np.quantile(depth_stack[0], 0.25))
        factor = 6.0 / focus
        log_min, log_max = np.log(depth_stack.min()), np.log(depth_stack.max())
        encoded = np.rint((np.log(depth_stack) - log_min) / (log_max - log_min) * 65535).astype('<u2')
        with gzip.open(destination / 'depth.bin.gz', 'wb', compresslevel=9) as file:
            file.write(encoded.tobytes())
        np.savez_compressed(destination / 'geometry.npz', depth=depth_stack,
            intrinsics=intrinsics, focus=focus, factor=factor)
        points = points_from_depth(depth_stack[0], intrinsics, factor, focus)
        faces = make_faces(width, height)
        if np.ptp(points[:, 2]) < 0.05:
            raise ValueError('Model output is effectively flat')
        entry = {
            'id': scene['id'], 'title': scene['title'], 'location': scene['location'],
            'caption': scene['moment'], 'source_start_s': start, 'source_end_s': end,
            'source_url': selection['source']['source_url'] + f'&t={int(start)}s',
            'fps': args.fps, 'frame_count': len(images), 'grid_width': width, 'grid_height': height,
            'intrinsics': intrinsics.tolist(), 'fov_y': math.degrees(2 * math.atan(0.5 / intrinsics[1, 1])),
            'focus': focus, 'factor': factor, 'log_depth_min': float(log_min), 'log_depth_max': float(log_max),
            'near_surface': float(np.quantile(depth_stack[0], 0.03) * factor),
            'vertex_count': len(points), 'triangle_count': len(faces),
            'depth_span': float(np.ptp(points[:, 2])),
            'poster': f'{scene["id"]}/frames/frame-000.jpg',
            'video': f'{scene["id"]}/source-motion.mp4',
            'depth': f'{scene["id"]}/depth.bin.gz',
            'glb': f'{scene["id"]}/scene.glb',
            'elapsed_seconds': round(time.monotonic() - scene_started, 2),
        }
        manifest['scenes'].append(entry)
        write(output / 'manifest.json', manifest)
    manifest['reconstruction_seconds'] = round(time.monotonic() - started, 2)
    manifest['reconstruction_complete'] = True
    write(output / 'manifest.json', manifest)
    write(args.run / 'status.json', {'phase': 'geometry_complete', 'scene_count': len(selected), 'stepfun_calls': 0})
    print('RECONSTRUCTION_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
