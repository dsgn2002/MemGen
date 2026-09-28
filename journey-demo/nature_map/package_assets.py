"""Package selected generated meshes and record geometry/bounds for scene assembly."""
import argparse
import json
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--assets', nargs='+', required=True)
    parser.add_argument('--clean-studio-floor', action='store_true')
    parser.add_argument('--packer', type=Path, default=Path('/home/Developer/travel_journey_map/vendor/meshoptimizer-0.25/gltfpack'))
    args = parser.parse_args()
    import trimesh
    import numpy as np
    packer = args.packer
    report = {}
    for name in args.assets:
        directory = args.run / 'output'
        source = directory / f'{name}.glb'
        temporary = directory / f'{name}.webp.glb'
        target = directory / f'{name}.web.glb'
        mesh = trimesh.load(source, force='scene')
        if not mesh.geometry:
            raise ValueError(f'Empty asset: {name}')
        removed = 0
        if args.clean_studio_floor:
            for geometry in mesh.geometry.values():
                height = geometry.extents[1]
                minimum = geometry.bounds[0, 1]
                keep = np.ones(len(geometry.faces), dtype=bool)
                for component in trimesh.graph.connected_components(geometry.face_adjacency, nodes=np.arange(len(geometry.faces)), min_len=1):
                    vertices = geometry.vertices[geometry.faces[component].reshape(-1)]
                    extent = np.ptp(vertices, axis=0)
                    if extent[1] < height * .02 and max(extent[0], extent[2]) > height * .5 and vertices[:, 1].max() < minimum + height * .06:
                        keep[component] = False
                removed += int((~keep).sum())
                geometry.update_faces(keep)
                geometry.remove_unreferenced_vertices()
        mesh.export(temporary, file_type='glb', extension_webp=True)
        subprocess.run([str(packer), '-i', str(temporary), '-o', str(target), '-cc'], check=True)
        temporary.unlink()
        report[name] = {'bounds':mesh.bounds.tolist(), 'triangles':sum(len(g.faces) for g in mesh.geometry.values()),
                        'removed_studio_floor_faces':removed, 'original_bytes':source.stat().st_size, 'browser_bytes':target.stat().st_size}
        print(name, report[name], flush=True)
    (args.run / 'analysis' / ('browser-' + args.assets[0] + '.json')).write_text(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
