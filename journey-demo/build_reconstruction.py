"""Assemble animated depth surfaces in Omniverse; export USD, GLB and RTX previews."""
import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path
import time
import zipfile

import numpy as np
from PIL import Image
import trimesh

from reconstruct_selected import make_faces, points_from_depth, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    output = run / 'output'
    manifest = json.loads((output / 'manifest.json').read_text())
    if not manifest.get('reconstruction_complete'):
        raise RuntimeError('Geometry reconstruction must finish before Omniverse assembly')
    write(run / 'status.json', {'phase': 'omniverse_assembly', 'stepfun_calls': 0})
    from omni.kit_app import KitApp
    app = KitApp()
    arguments = ['--no-window', '--enable', 'omni.usd', '--/app/telemetry/enable=false',
        '--/renderer/active=rtx', '--/renderer/enabled=rtx',
        '--/app/renderer/skipWhileMinimized=false', '--/app/window/width=960', '--/app/window/height=540']
    for extension in ['omni.hydra.rtx', 'omni.kit.uiapp', 'omni.kit.viewport.window', 'omni.kit.viewport.utility']:
        arguments.extend(['--enable', extension])
    app.startup(arguments)
    try:
        import carb
        import omni.usd
        import omni.timeline
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt
        from omni.kit.viewport.utility import create_viewport_window, capture_viewport_to_file
        usd_path = output / 'my-travel-journey.usdc'
        stage = Usd.Stage.CreateNew(str(usd_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.SetTimeCodesPerSecond(24)
        stage.SetFramesPerSecond(24)
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(max((s['frame_count'] - 1) * 24 / s['fps'] for s in manifest['scenes']))
        root = UsdGeom.Xform.Define(stage, '/World')
        stage.SetDefaultPrim(root.GetPrim())
        stage.GetRootLayer().customLayerData = {
            'title': manifest['title'], 'source_url': manifest['source']['source_url'],
            'method': manifest['method'], 'limitations': '\n'.join(manifest['limitations']),
            'stepfun_calls': 0,
        }
        paths = {}
        for entry in manifest['scenes']:
            scene_id = entry['id']
            name = scene_id.replace('-', '_')
            path = '/World/' + name
            paths[scene_id] = path
            group = UsdGeom.Xform.Define(stage, path)
            group.GetPrim().SetCustomDataByKey('title', entry['title'])
            group.GetPrim().SetCustomDataByKey('source_timestamp_seconds', entry['source_start_s'])
            data = np.load(output / scene_id / 'geometry.npz')
            faces = make_faces(entry['grid_width'], entry['grid_height'])
            mesh = UsdGeom.Mesh.Define(stage, path + '/Surface')
            mesh.CreateFaceVertexCountsAttr([3] * len(faces))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(faces.flatten()))
            mesh.CreateSubdivisionSchemeAttr('none')
            mesh.CreateDoubleSidedAttr(True)
            u, v = np.meshgrid((np.arange(entry['grid_width']) + .5) / entry['grid_width'],
                               (np.arange(entry['grid_height']) + .5) / entry['grid_height'])
            uv = np.stack([u, 1 - v], axis=-1).reshape(-1, 2).astype(np.float32)
            st = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'vertex')
            st.Set(Vt.Vec2fArray.FromNumpy(uv))
            point_attr = mesh.CreatePointsAttr()
            extent_attr = mesh.CreateExtentAttr()
            for frame, depth in enumerate(data['depth']):
                points = points_from_depth(depth, data['intrinsics'], float(data['factor']), float(data['focus']))
                array = Vt.Vec3fArray.FromNumpy(points)
                extent = Vt.Vec3fArray.FromNumpy(np.stack([points.min(axis=0), points.max(axis=0)]))
                if frame == 0:
                    point_attr.Set(array)
                    extent_attr.Set(extent)
                point_attr.Set(array, frame * 24 / entry['fps'])
                extent_attr.Set(extent, frame * 24 / entry['fps'])
            mat_path = '/World/Looks/' + name
            material = UsdShade.Material.Define(stage, mat_path)
            shader = UsdShade.Shader.Define(stage, mat_path + '/Surface')
            shader.CreateIdAttr('UsdPreviewSurface')
            shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0))
            shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(1)
            texture = UsdShade.Shader.Define(stage, mat_path + '/Texture')
            texture.CreateIdAttr('UsdUVTexture')
            texture.CreateInput('sourceColorSpace', Sdf.ValueTypeNames.Token).Set('sRGB')
            texture.CreateInput('wrapS', Sdf.ValueTypeNames.Token).Set('clamp')
            texture.CreateInput('wrapT', Sdf.ValueTypeNames.Token).Set('clamp')
            texture.CreateOutput('rgb', Sdf.ValueTypeNames.Float3)
            file_attr = texture.CreateInput('file', Sdf.ValueTypeNames.Asset)
            file_attr.Set(Sdf.AssetPath(entry['poster']))
            for frame in range(entry['frame_count']):
                file_attr.Set(Sdf.AssetPath(f'{scene_id}/frames/frame-{frame:03d}.jpg'), frame * 24 / entry['fps'])
            reader = UsdShade.Shader.Define(stage, mat_path + '/UV')
            reader.CreateIdAttr('UsdPrimvarReader_float2')
            reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
            reader.CreateOutput('result', Sdf.ValueTypeNames.Float2)
            texture.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), 'result')
            shader.CreateInput('emissiveColor', Sdf.ValueTypeNames.Color3f).ConnectToSource(texture.ConnectableAPI(), 'rgb')
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
            UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
            camera = UsdGeom.Camera.Define(stage, path + '/Camera')
            camera.CreateProjectionAttr('perspective')
            camera.CreateHorizontalApertureAttr(36)
            camera.CreateVerticalApertureAttr(36 * 9 / 16)
            camera.CreateFocalLengthAttr(36 * float(data['intrinsics'][0, 0]))
            camera.CreateClippingRangeAttr(Gf.Vec2f(.001, 100000))
            op = UsdGeom.Xformable(camera).AddTransformOp()
            op.Set(Gf.Matrix4d().SetTranslate(Gf.Vec3d(0, 0, 6)))
            for frame in range(entry['frame_count']):
                # A restrained camera move preserves the usable source viewpoint.
                phase = frame / max(1, entry['frame_count'] - 1) * 2 * np.pi
                amplitude = min(.16, entry['near_surface'] * .035)
                eye = Gf.Vec3d(amplitude * np.sin(phase), amplitude * .3 * (np.cos(phase) - 1), 6)
                view = Gf.Matrix4d().SetLookAt(eye, Gf.Vec3d(0), Gf.Vec3d(0, 1, 0))
                op.Set(view.GetInverse(), frame * 24 / entry['fps'])
        variants = root.GetPrim().GetVariantSets().AddVariantSet('scene')
        for entry in manifest['scenes']:
            variants.AddVariant(entry['id'])
            variants.SetVariantSelection(entry['id'])
            with variants.GetVariantEditContext():
                for other in manifest['scenes']:
                    UsdGeom.Imageable(stage.GetPrimAtPath(paths[other['id']])).CreateVisibilityAttr().Set(
                        'inherited' if other['id'] == entry['id'] else 'invisible')
        variants.SetVariantSelection(manifest['scenes'][0]['id'])
        stage.GetRootLayer().Save()
        reopened = Usd.Stage.Open(str(usd_path))
        report = {'kit_version': importlib.metadata.version('omniverse-kit'), 'stepfun_calls': 0,
                  'usd_reload': True, 'scenes': [], 'renderer': 'pending'}
        for entry in manifest['scenes']:
            usd_mesh = UsdGeom.Mesh(reopened.GetPrimAtPath(paths[entry['id']] + '/Surface'))
            points = np.asarray(usd_mesh.GetPointsAttr().Get(0))
            faces = np.asarray(usd_mesh.GetFaceVertexIndicesAttr().Get()).reshape(-1, 3)
            uv = np.asarray(UsdGeom.PrimvarsAPI(usd_mesh).GetPrimvar('st').Get())
            photo = Image.open(output / entry['poster']).convert('RGB')
            material = trimesh.visual.material.PBRMaterial(baseColorTexture=photo,
                emissiveTexture=photo, emissiveFactor=[1, 1, 1], roughnessFactor=1, metallicFactor=0,
                doubleSided=True)
            mesh = trimesh.Trimesh(vertices=points, faces=faces,
                visual=trimesh.visual.TextureVisuals(uv=uv, material=material), process=False)
            glb_path = output / entry['glb']
            mesh.export(glb_path)
            restored = trimesh.load(glb_path, force='scene')
            assert len(restored.geometry) == 1 and np.isfinite(restored.bounds).all()
            assert len(usd_mesh.GetPointsAttr().GetTimeSamples()) == entry['frame_count']
            assert np.max(np.abs(np.asarray(usd_mesh.GetPointsAttr().Get(0)) - np.asarray(usd_mesh.GetPointsAttr().Get(3)))) > 0
            report['scenes'].append({'id': entry['id'], 'vertices': len(points), 'triangles': len(faces),
                'animation_samples': entry['frame_count'], 'depth_span': float(np.ptp(points[:, 2])),
                'glb_reload': True, 'glb_bytes': glb_path.stat().st_size})
        context = omni.usd.get_context()
        context.open_stage(str(usd_path))
        stage = context.get_stage()
        # Linear tonemapping still applies camera exposure. Operator 0 bypasses
        # exposure and clips the RTX radiometric emission values to white.
        settings = carb.settings.get_settings()
        render_settings = {
            '/rtx/post/tonemap/op': 1,
            '/rtx/post/tonemap/filmIso': 100.0,
            '/rtx/post/tonemap/cameraShutter': 50.0,
            '/rtx/post/tonemap/fNumber': 5.0,
            '/rtx/post/histogram/enabled': False,
            '/rtx/post/tonemap/enableSrgbToGamma': True,
        }
        for key, value in render_settings.items():
            settings.set(key, value)
        report['render_settings'] = render_settings
        viewport_window = create_viewport_window('My Travel Journey', width=960, height=540)
        viewport = viewport_window.viewport_api
        viewport.fill_frame = False
        viewport.resolution = (960, 540)
        viewport.updates_enabled = True
        timeline = omni.timeline.get_timeline_interface()
        variants = stage.GetPrimAtPath('/World').GetVariantSets().GetVariantSet('scene')
        for entry in manifest['scenes']:
            variants.SetVariantSelection(entry['id'])
            viewport.camera_path = paths[entry['id']] + '/Camera'
            for frame, label in [(0, 'preview'), (6, 'motion-preview')]:
                timeline.set_current_time(frame / entry['fps'])
                for _ in range(90):
                    app.update()
                target = output / entry['id'] / (label + '.png')
                capture = capture_viewport_to_file(viewport, str(target))
                future = asyncio.ensure_future(capture.wait_for_result(completion_frames=20))
                deadline = time.monotonic() + 120
                while not future.done() and time.monotonic() < deadline:
                    app.update()
                if not future.done():
                    raise TimeoutError('RTX preview timed out')
                future.result()
                assert target.is_file() and target.stat().st_size > 1000
                pixels = np.asarray(Image.open(target).convert('RGB'))
                white_fraction = float(np.mean(np.all(pixels > 250, axis=-1)))
                if white_fraction > .8 or float(pixels.std()) < 8:
                    raise ValueError(f'RTX preview has insufficient visual detail: {target.name}')
                print(f'RTX_PREVIEW {entry["id"]} {label}', flush=True)
            entry['omniverse_preview'] = entry['id'] + '/preview.png'
        variants.SetVariantSelection(manifest['scenes'][0]['id'])
        timeline.set_current_time(0)
        stage.GetRootLayer().Save()
        report['renderer'] = 'NVIDIA Omniverse RTX'
        report['preview_count'] = 6
        write(output / 'build-report.json', report)
        manifest['omniverse_complete'] = True
        manifest['usd'] = usd_path.name
        manifest['usd_bundle'] = 'my-travel-journey-omniverse.zip'
        write(output / 'manifest.json', manifest)
        with zipfile.ZipFile(output / manifest['usd_bundle'], 'w', zipfile.ZIP_DEFLATED) as bundle:
            for path in [usd_path, output / 'manifest.json', output / 'build-report.json']:
                bundle.write(path, path.relative_to(output))
            for path in sorted(output.glob('*/frames/*.jpg')):
                bundle.write(path, path.relative_to(output))
        write(run / 'status.json', {'phase': 'complete', 'stepfun_calls': 0, 'scene_count': len(manifest['scenes'])})
        print('OMNIVERSE_COMPLETE ' + json.dumps(report), flush=True)
    except Exception as error:
        write(run / 'status.json', {'phase': 'failed', 'error': str(error), 'stepfun_calls': 0})
        raise
    finally:
        app.shutdown()


if __name__ == '__main__':
    main()
