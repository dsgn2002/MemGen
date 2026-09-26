"""Assemble generated full 3D assets and a boat animation in NVIDIA Omniverse."""
import asyncio
import json
import math
import os
import shutil
import time
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

ROOT = Path('/home/Developer/travel_journey_map')
RUN = ROOT / 'runs/2026-09-26-sai-kung-map'
OUT = RUN / 'output'
os.environ.update(OMNI_KIT_ACCEPT_EULA='yes', VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/nvidia_icd.json')


def traveler_position():
    """Place feet on the terrain using a vertical triangle intersection."""
    scene = trimesh.load(OUT / 'coast.glb', force='scene')
    center, factor = scene.bounds.mean(axis=0), 12 / max(scene.extents)
    heights = []
    x, z = -3.0, 0.0
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        triangles = ((mesh.vertices - center) * factor)[mesh.faces]
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        denominator = (b[:, 2]-c[:, 2])*(a[:, 0]-c[:, 0]) + (c[:, 0]-b[:, 0])*(a[:, 2]-c[:, 2])
        with np.errstate(divide='ignore', invalid='ignore'):
            u = ((b[:, 2]-c[:, 2])*(x-c[:, 0]) + (c[:, 0]-b[:, 0])*(z-c[:, 2])) / denominator
            v = ((c[:, 2]-a[:, 2])*(x-c[:, 0]) + (a[:, 0]-c[:, 0])*(z-c[:, 2])) / denominator
        w = 1-u-v
        inside = (u >= 0) & (v >= 0) & (w >= 0)
        heights.extend((u[inside]*a[inside, 1] + v[inside]*b[inside, 1] + w[inside]*c[inside, 1]).tolist())
    if not heights:
        raise RuntimeError('Traveler placement misses terrain')
    return (x, max(heights) + 1.45 + .7 + .02, z)


def main():
    from omni.kit_app import KitApp
    app = KitApp()
    args = ['--no-window', '--enable', 'omni.usd', '--/app/telemetry/enable=false',
            '--/renderer/active=rtx', '--/renderer/enabled=rtx']
    for extension in ['omni.hydra.rtx', 'omni.kit.uiapp', 'omni.kit.viewport.window', 'omni.kit.viewport.utility']:
        args += ['--enable', extension]
    app.startup(args)
    try:
        import carb
        import omni.usd
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdLux, Vt
        from omni.kit.viewport.utility import create_viewport_window, capture_viewport_to_file
        stage = Usd.Stage.CreateNew(str(OUT / 'scene.usdc'))
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(480)
        stage.SetTimeCodesPerSecond(24)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1)
        world = UsdGeom.Xform.Define(stage, '/World')
        stage.SetDefaultPrim(world.GetPrim())
        stats = {}
        (OUT / 'textures').mkdir(exist_ok=True)
        traveler = traveler_position()
        (OUT / 'scene-layout.json').write_text(json.dumps({'traveler_position': traveler}, indent=2))
        for name, size, position in [('coast', 12, (0, 1.45, 0)), ('traveler', 1.4, traveler), ('boat', 2.1, (-6, .42, 5))]:
            loaded = trimesh.load(OUT / f'{name}.glb', force='scene')
            center = loaded.bounds.mean(axis=0)
            factor = size / np.max(loaded.extents)
            group = UsdGeom.Xform.Define(stage, '/World/' + name)
            translate = group.AddTranslateOp()
            translate.Set(Gf.Vec3d(*position))
            rotate = group.AddRotateYOp()
            rotate.Set(20 if name == 'traveler' else 0)
            if name == 'boat':
                for frame in range(0, 481, 8):
                    t = frame / 24
                    theta = t * math.pi / 20
                    translate.Set(Gf.Vec3d(-6 * math.cos(theta), .42 + .035 * math.sin(t * 1.8), 5 + 1.5 * math.sin(theta)), frame)
                    rotate.Set(float(90 - theta * 180 / math.pi), frame)
            faces_count = 0
            for index, node in enumerate(loaded.graph.nodes_geometry):
                transform, geometry_name = loaded.graph[node]
                source = loaded.geometry[geometry_name].copy()
                source.apply_transform(transform)
                vertices = ((source.vertices - center) * factor).astype(np.float32)
                faces = np.asarray(source.faces, np.int32)
                faces_count += len(faces)
                path = f'/World/{name}/Mesh_{index}'
                mesh = UsdGeom.Mesh.Define(stage, path)
                mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(vertices))
                mesh.CreateFaceVertexCountsAttr([3] * len(faces))
                mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(faces.flatten()))
                mesh.CreateSubdivisionSchemeAttr('none')
                mesh.CreateDoubleSidedAttr(True)
                mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(np.asarray(source.vertex_normals, np.float32)))
                mesh.SetNormalsInterpolation('vertex')
                material = UsdShade.Material.Define(stage, f'/World/Looks/{name}_{index}')
                shader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild('Surface'))
                shader.CreateIdAttr('UsdPreviewSurface')
                shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(.7)
                shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(0)
                shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.6, .7, .55))
                if hasattr(source.visual, 'uv') and source.visual.uv is not None:
                    uv = np.asarray(source.visual.uv, np.float32)
                    UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, 'vertex').Set(Vt.Vec2fArray.FromNumpy(uv))
                    source_mat = source.visual.material
                    texture = getattr(source_mat, 'baseColorTexture', None)
                    if texture is None:
                        texture = getattr(source_mat, 'image', None)
                    if texture is not None:
                        texture_name = f'{name}_{index}.png'
                        texture.save(OUT / 'textures' / texture_name)
                        reader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild('UV'))
                        reader.CreateIdAttr('UsdPrimvarReader_float2')
                        reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
                        reader.CreateOutput('result', Sdf.ValueTypeNames.Float2)
                        tex = UsdShade.Shader.Define(stage, material.GetPath().AppendChild('Texture'))
                        tex.CreateIdAttr('UsdUVTexture')
                        tex.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath('textures/' + texture_name))
                        tex.CreateInput('sourceColorSpace', Sdf.ValueTypeNames.Token).Set('sRGB')
                        tex.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), 'result')
                        tex.CreateOutput('rgb', Sdf.ValueTypeNames.Float3)
                        shader.GetInput('diffuseColor').ConnectToSource(tex.ConnectableAPI(), 'rgb')
                material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
                UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
            stats[name] = {'triangles': faces_count, 'size': size}
        ocean = UsdGeom.Mesh.Define(stage, '/World/Water')
        ocean.CreatePointsAttr([(-300, -.12, -300), (300, -.12, -300), (300, -.12, 300), (-300, -.12, 300)])
        ocean.CreateFaceVertexCountsAttr([4])
        ocean.CreateFaceVertexIndicesAttr([0, 3, 2, 1])
        ocean.CreateDisplayColorAttr([Gf.Vec3f(.04, .48, .47)])
        dome = UsdLux.DomeLight.Define(stage, '/World/Sky')
        dome.CreateIntensityAttr(650)
        sun = UsdLux.DistantLight.Define(stage, '/World/Sun')
        sun.CreateIntensityAttr(2300)
        sun.CreateAngleAttr(12)
        UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(-45, -30, 0))
        camera = UsdGeom.Camera.Define(stage, '/World/Camera')
        camera.CreateHorizontalApertureAttr(36)
        camera.CreateVerticalApertureAttr(24)
        camera.CreateFocalLengthAttr(32)
        matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(15, 13, 18), Gf.Vec3d(0, 1, 0), Gf.Vec3d(0, 1, 0)).GetInverse()
        UsdGeom.Xformable(camera).AddTransformOp().Set(matrix)
        stage.GetRootLayer().Save()
        context = omni.usd.get_context()
        context.open_stage(str(OUT / 'scene.usdc'))
        for _ in range(60):
            app.update()
        settings = carb.settings.get_settings()
        for key, value in {'/rtx/post/tonemap/op': 6, '/rtx/post/tonemap/filmIso': 100.0,
                '/rtx/post/tonemap/cameraShutter': 50.0, '/rtx/post/tonemap/fNumber': 5.0,
                '/rtx/post/histogram/enabled': False, '/rtx/post/tonemap/enableSrgbToGamma': True}.items():
            settings.set(key, value)
        viewport = create_viewport_window('Sai Kung nature map', width=1200, height=800).viewport_api
        viewport.camera_path = '/World/Camera'
        viewport.resolution = (1200, 800)
        for _ in range(120):
            app.update()
        target = OUT / 'omniverse-preview.png'
        capture = capture_viewport_to_file(viewport, str(target))
        future = asyncio.ensure_future(capture.wait_for_result(completion_frames=20))
        deadline = time.monotonic() + 120
        while not future.done() and time.monotonic() < deadline:
            app.update()
        if not future.done():
            raise TimeoutError('RTX capture timed out')
        future.result()
        if float(np.asarray(Image.open(target)).std()) < 5:
            raise RuntimeError('Blank render')
        reloaded = Usd.Stage.Open(str(OUT / 'scene.usdc'))
        assert reloaded.GetPrimAtPath('/World/coast').IsValid()
        assert len(reloaded.GetPrimAtPath('/World/boat').GetAttribute('xformOp:translate').GetTimeSamples()) > 2
        manifest = {'title': 'Sai Kung · My Travel Journey', 'models': ['Qwen3.6-27B', 'Qwen-Image-Edit-2511', 'TRELLIS.2-4B'],
            'omniverse_complete': True, 'assets': stats, 'source': 'https://www.youtube.com/watch?v=9jtnoejpLcU',
            'source_timestamps': [60, 80, 98], 'animation': ['boat transform', 'browser water and ripples'],
            'limitations': ['artistic spatial layout, not navigation geography', 'traveler is posed, not skeletally animated', 'unseen sides are model-generated'],
            'paid_api_calls': 0}
        (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        with zipfile.ZipFile(OUT / 'scene-bundle.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in [OUT / 'scene.usdc', OUT / 'manifest.json', OUT / 'scene-layout.json', *sorted((OUT / 'textures').glob('*.png'))]:
                archive.write(path, path.relative_to(OUT))
        (OUT / 'memories').mkdir(exist_ok=True)
        for stamp in [60, 80, 98]:
            shutil.copy2(RUN / f'input/frame-{stamp}.jpg', OUT / f'memories/frame-{stamp}.jpg')
        print('OMNIVERSE_COMPLETE', json.dumps(manifest), flush=True)
    finally:
        app.shutdown()


if __name__ == '__main__':
    main()
