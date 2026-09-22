"""Compile a validated Step 5 design into an Omniverse USD stage and a GLB."""
import argparse
import asyncio
import importlib.metadata
import json
import math
from pathlib import Path
import time

import numpy as np
import trimesh

from analyze import validate_world, write_json


def primitive(shape, scale, position, rotation):
    if shape == 'box':
        mesh = trimesh.creation.box()
    elif shape == 'sphere':
        mesh = trimesh.creation.icosphere(subdivisions=1)
    elif shape == 'cylinder':
        mesh = trimesh.creation.cylinder(radius=0.5, height=1, sections=12)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
    elif shape == 'cone':
        mesh = trimesh.creation.cone(radius=0.5, height=1, sections=10)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))
    else:
        raise ValueError(f'Unsupported shape: {shape}')
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    mesh.apply_scale(np.asarray(scale) / mesh.extents)
    mesh.apply_transform(trimesh.transformations.euler_matrix(*np.radians(rotation), axes='sxyz'))
    mesh.apply_translation(position)
    return mesh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    run = args.run.resolve()
    world = json.loads((run / 'analysis/world_spec.json').read_text())
    source = json.loads((run / 'input/source.json').read_text())
    checks = validate_world(world, source['duration_seconds'])
    output = run / 'output'
    output.mkdir(exist_ok=True)

    # The caller accepts NVIDIA's EULA before invoking this executable.
    from omni.kit_app import KitApp
    app = KitApp()
    arguments = ['--no-window', '--enable', 'omni.usd', '--/app/telemetry/enable=false']
    if args.render:
        for extension in ['omni.hydra.rtx', 'omni.kit.uiapp', 'omni.kit.viewport.window', 'omni.kit.viewport.utility']:
            arguments.extend(['--enable', extension])
        arguments.extend(['--/renderer/active=rtx', '--/renderer/enabled=rtx', '--/app/renderer/skipWhileMinimized=false', '--/app/window/width=1280', '--/app/window/height=800'])
    app.startup(arguments)
    try:
        import omni.usd
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade, Vt, Tf

        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        root = UsdGeom.Xform.Define(stage, '/World')
        stage.SetDefaultPrim(root.GetPrim())
        stage.GetRootLayer().customLayerData = {'title': world['title'], 'source_url': source['source_url'], 'generator': 'Step 5 design compiled in NVIDIA Omniverse Kit'}
        materials = {}
        paths = []

        def add_mesh(path, mesh, color, role=''):
            if not np.isfinite(mesh.vertices).all():
                raise ValueError('Non-finite vertex')
            usd = UsdGeom.Mesh.Define(stage, path)
            usd.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.asarray(mesh.vertices, dtype=np.float32)))
            usd.CreateFaceVertexCountsAttr([3] * len(mesh.faces))
            usd.CreateFaceVertexIndicesAttr(mesh.faces.flatten().tolist())
            usd.CreateSubdivisionSchemeAttr('none')
            usd.CreateDoubleSidedAttr(True)
            rgb = np.array([int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)])
            linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
            usd.CreateDisplayColorAttr([Gf.Vec3f(*linear)])
            usd.GetPrim().SetCustomDataByKey('srgb_color', color)
            usd.GetPrim().SetCustomDataByKey('role', role)
            if color not in materials:
                mat_path = '/Materials/C' + color[1:]
                material = UsdShade.Material.Define(stage, mat_path)
                shader = UsdShade.Shader.Define(stage, mat_path + '/Surface')
                shader.CreateIdAttr('UsdPreviewSurface')
                shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*linear))
                shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(0.75)
                shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(0)
                material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
                materials[color] = material
            UsdShade.MaterialBindingAPI.Apply(usd.GetPrim()).Bind(materials[color])
            paths.append(path)

        for index, stop in enumerate(world['stops']):
            origin = np.array(stop['position'], dtype=float)
            stop_path = f'/World/Stops/S{index}_{Tf.MakeValidIdentifier(stop["id"])}'
            stop_prim = UsdGeom.Xform.Define(stage, stop_path).GetPrim()
            stop_prim.SetCustomDataByKey('caption', stop['caption'])
            stop_prim.SetCustomDataByKey('label', stop['label'])
            for name, size, height, color in [('Island', [8.4, 0.65, 8.4], -0.325, '#E4CBA0'), ('Rim', [8.55, 0.12, 8.55], -0.7, '#B98C5D')]:
                add_mesh(stop_path + '/' + name, primitive('cylinder', size, origin + [0, height, 0], [0, 0, 0]), color, 'souvenir island base')
            for index_part, part in enumerate(stop['parts']):
                position = origin + np.asarray(part['position'])
                path = stop_path + f'/P{index_part}_' + Tf.MakeValidIdentifier(part['id'])
                add_mesh(path, primitive(part['shape'], part['scale'], position, part.get('rotation_deg', [0, 0, 0])), part['color'], part.get('role', ''))

        # A dotted path links the miniature islands; this is a designed layout.
        for index, (left, right) in enumerate(zip(world['stops'], world['stops'][1:])):
            a, b = np.asarray(left['position'], dtype=float), np.asarray(right['position'], dtype=float)
            for dot, t in enumerate(np.linspace(0.35, 0.65, 8)):
                position = a * (1 - t) + b * t + [0, -0.4, 0]
                add_mesh(f'/World/Route/R{index}_{dot}', primitive('sphere', [0.14, 0.14, 0.14], position, [0, 0, 0]), '#CB8050', 'journey route')

        dome = UsdLux.DomeLight.Define(stage, '/Lighting/Ambient')
        dome.CreateIntensityAttr(650)
        dome.CreateColorAttr(Gf.Vec3f(0.93, 0.97, 1.0))
        sun = UsdLux.DistantLight.Define(stage, '/Lighting/Sun')
        sun.CreateIntensityAttr(2200)
        sun.CreateAngleAttr(12)
        UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-35, -30, 0))
        camera = UsdGeom.Camera.Define(stage, '/Camera')
        camera.CreateProjectionAttr('orthographic')
        camera.CreateHorizontalApertureAttr(400)
        camera.CreateVerticalApertureAttr(250)
        camera.CreateClippingRangeAttr(Gf.Vec2f(0.1, 2000))
        view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(22, 26, 34), Gf.Vec3d(0, 1, 0), Gf.Vec3d(0, 1, 0))
        UsdGeom.Xformable(camera).AddTransformOp().Set(view.GetInverse())
        usd_path = output / 'my-travel-journey.usda'
        stage.GetRootLayer().Export(str(usd_path))

        # Export the meshes read back from the actual USD stage for the browser.
        reopened = Usd.Stage.Open(str(usd_path))
        scene = trimesh.Scene()
        triangles = 0
        for path in paths:
            usd = UsdGeom.Mesh(reopened.GetPrimAtPath(path))
            vertices = np.asarray(usd.GetPointsAttr().Get())
            faces = np.asarray(usd.GetFaceVertexIndicesAttr().Get()).reshape(-1, 3)
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            # glTF baseColorFactor, like the USD shader input, is linear RGB.
            rgba = np.array([*usd.GetDisplayColorAttr().Get()[0], 1.0], dtype=float)
            mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(baseColorFactor=rgba, roughnessFactor=0.8, metallicFactor=0.0, doubleSided=True))
            scene.add_geometry(mesh, node_name=path, geom_name=path)
            triangles += len(faces)
        glb_path = output / 'my-travel-journey.glb'
        scene.export(glb_path)
        loaded = trimesh.load(glb_path, force='scene')
        if len(loaded.geometry) != len(paths) or not np.isfinite(loaded.bounds).all():
            raise ValueError('GLB round-trip validation failed')
        checks.update({'kit_version': importlib.metadata.version('omniverse-kit'), 'usd_mesh_count': len(paths), 'glb_mesh_count': len(loaded.geometry), 'triangles': triangles, 'glb_bytes': glb_path.stat().st_size, 'renderer': 'not requested', 'usd_reload': 'passed', 'glb_reload': 'passed'})
        write_json(output / 'build_report.json', checks)
        print('USD_AND_GLB_GENERATED ' + json.dumps(checks), flush=True)

        if args.render:
            from omni.kit.viewport.utility import create_viewport_window, capture_viewport_to_file
            viewport_window = create_viewport_window('My Travel Journey', width=1280, height=800)
            viewport = viewport_window.viewport_api
            viewport.fill_frame = False
            viewport.camera_path = '/Camera'
            viewport.resolution = (1280, 800)
            viewport.updates_enabled = True
            for _ in range(120):
                app.update()
            capture = capture_viewport_to_file(viewport, str(output / 'preview.png'))
            future = asyncio.ensure_future(capture.wait_for_result(completion_frames=30))
            deadline = time.monotonic() + 120
            while not future.done() and time.monotonic() < deadline:
                app.update()
            if not future.done():
                raise TimeoutError('Omniverse viewport capture exceeded 120 seconds')
            future.result()
            if not (output / 'preview.png').exists():
                raise RuntimeError('Omniverse did not save the preview image')
            checks['renderer'] = 'NVIDIA Omniverse RTX viewport'
            write_json(output / 'build_report.json', checks)
            print('RTX_PREVIEW_SAVED', flush=True)
    except Exception as error:
        write_json(output / 'build_error.json', {'type': type(error).__name__, 'message': str(error)})
        print('BUILD_FAILED ' + type(error).__name__ + ': ' + str(error), flush=True)
        raise
    finally:
        app.shutdown()


if __name__ == '__main__':
    main()
