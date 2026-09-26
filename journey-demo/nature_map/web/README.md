# Two sides of Hong Kong

This revision adds three separate source-conditioned passengers to the Sai Kung boat,
a Hong Kong tram scene, and coordinated daylight, sunset, and night atmospheres.
The rendered people have approximate appearances and poses. The city pedestrians
are illustrative additions; the city layout is a composition, not a map survey.

`scene-plan.json` records the required passenger count, clothing cues, source timestamps,
boat attachment relationship, city details, and creative additions. It is a manually
reviewed sample plan, not yet an automated upload-to-scene service.

## Generate the additional assets on the existing Spark

The existing environment and local weights described in the parent README are required.
The two specifications use the fixed run `runs/2026-09-26-diverse-demo` and reference
frames in its `input/` directory. `frame-60.jpg` is the 1280×720 boat reference;
city references `frame-50.jpg` and `frame-435.jpg` are from the separate tram video.

Run large models sequentially to release their memory between stages:

```bash
python scripts/style_assets.py --spec scripts/passenger-spec.json
python scripts/generate_meshes.py --run runs/2026-09-26-diverse-demo \
  --assets passenger-white passenger-dark passenger-orange --triangles 30000 --texture-size 1024
python scripts/package_assets.py --run runs/2026-09-26-diverse-demo \
  --assets passenger-white passenger-dark passenger-orange --clean-studio-floor
python scripts/style_assets.py --spec scripts/city-spec.json
python scripts/generate_meshes.py --run runs/2026-09-26-diverse-demo \
  --assets city-buildings city-tram --triangles 70000 --texture-size 2048
python scripts/package_assets.py --run runs/2026-09-26-diverse-demo \
  --assets city-buildings city-tram --clean-studio-floor
```

The floor-cleaning option removes only separate, broad, very thin components at the
bottom of an asset. It retains the original GLB and records the number of removed faces
in packaging provenance. Styled images, generation timings, and geometry provenance
remain in the run. Existing output images and meshes are reused on rerun.

## Viewer layout

Serve these files over HTTP, with the following generated files beside them:

- `coast.web.glb`, `traveler.web.glb`, `boat.web.glb`: original Sai Kung assets.
- `passenger-white.web.glb`, `passenger-dark.web.glb`, `passenger-orange.web.glb`.
- `memories/frame-60.jpg`, `frame-80.jpg`, `frame-98.jpg`: original source memories.
- `city/city-buildings.web.glb`, `city/city-tram.web.glb`.
- `city/frame-50.jpg`, `frame-190.jpg`, `frame-435.jpg`: tram-video source memories.

`?scene=coast` and `?scene=city` select the experience. People are attached to the boat
as children of its animated transform. The optional canopy cutaway clips the boat
roof for inspection. Atmospheric changes affect sky, directional and fill lights,
stars, emissive lamps, bloom, and procedural water reflections. The revised interactive
assembly runs in Three.js; the original coast retains its earlier Omniverse output.

The public viewer is published separately at
https://dsgn2002.github.io/sai-kung-3d-viewer/demo/.
The project page's absolute HTTPS embed also works when its HTML is opened locally.
The viewer itself needs HTTP(S) for modules and mesh fetches.

## Validation

```bash
PLAYWRIGHT_MODULE=/path/to/playwright node journey-demo/nature_map/check_diverse_viewer.cjs \
  http://127.0.0.1:8788/demo/ tmp/diverse-qa
```

Checks cover successful loading, three distinct boat passengers, attachment to the boat,
animation and pause, lighting/stars, source images, canopy inspection, browser errors,
and mobile overflow. Rendered views must also be reviewed for scale, occlusion, placement,
and the preservation of source details. Screenshots and a JSON validation record are saved.

## City source

[Hong Kong Trams, September 2009](https://commons.wikimedia.org/wiki/File:Hong_Kong_Trams,_September_2009-UKNqZzl2cu8.webm)
by michaelinlondon, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
Source frames are extracted and transformed into stylized assets. The scene includes
an authored road layout, illustrative pedestrians, and alternate lighting.
