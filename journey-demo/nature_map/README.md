# Sai Kung nature map

The [two-scene revision](web/README.md) adds the three missing boat passengers,
a Hong Kong tram-travel sample, and daylight/sunset/night controls. The original
run documented below remains available as generation provenance.

This sample uses local Qwen image/video understanding, Qwen image editing, and
TRELLIS.2 asset generation on DGX Spark. The output target is an interactive
stylized 3D travel map with independent terrain, traveler, and boat meshes.

This is a working sample for the existing Spark installation, not a general
upload service or a one-command fresh-machine installer. Paths and timestamps
are fixed to this run. Video understanding uses nine sampled frames, without
audio transcription. The VLM summary informs review; the three selections,
style prompts, and map composition are authored in the sample scripts.

The source is the existing Travel Intern Hong Kong video. The selected memories
are the Sai Kung boat tour (60 s), High Island Reservoir (80 s), and MacLehose
coastal trail (98 s). The video also contains other Hong Kong chapters; those are
excluded from this sample map.

## Stages

1. `understand_and_style.py extract` extracts chronological source frames.
2. `understand_and_style.py understand` runs Qwen3.6-27B on those frames and saves
   the actual model response, structured summary, prompt, and timing.
3. `understand_and_style.py style` runs Qwen-Image-Edit-2511 on source frames to
   create three isolated designs: coast, traveler, and green-canopy boat.
4. `generate_meshes.py` runs TRELLIS.2-4B at 512 resolution and exports textured
   GLB assets. It saves the raw inferred geometry and per-asset provenance.
5. `assemble_omniverse.py` assembles the assets in Omniverse, adds boat transform
   animation, captures an RTX preview, and exports a USD scene with textures.
6. `package_browser.py` creates compact GLBs with WebP textures and Meshopt
   compression while retaining the original editable meshes.
7. `viewer.html` loads those GLBs into an interactive browser map. It provides
   rotation, zoom, scale, clickable source memories, moving boat, water/ripples,
   animation pause, and lighting controls.

The final scene is an artistic composition, not geographic reconstruction or a
navigation map. Hidden surfaces are generated. The traveler is a posed 3D
character, with approximate appearance from a small source frame. Skeletal
walking/waving animation is not part of this sample.

The completed run contains 349,851 triangles: coast 118,536, traveler 116,063,
and boat 115,252. The three browser assets total 4,634,568 bytes; the original
GLBs total 32,215,368 bytes. `scene-bundle.zip` contains editable OpenUSD and its
textures. `scene-layout.json` shares the terrain-grounded traveler placement
between Omniverse and the browser.

## Spark environment

Project root: `/home/Developer/travel_journey_map`.

Run directory: `runs/2026-09-26-sai-kung-map`.

Python: `/home/Developer/miniforge3/envs/travel_journey_map/bin/python`.

The runtime uses PyTorch 2.10.0+cu130, Transformers 5.17.0, Diffusers 0.40.0,
CUDA 13, and the previously installed Omniverse Kit. The model weights remain
on Spark. No StepFun credentials are loaded and no paid inference API is used.

TRELLIS requires FlexGEMM, CuMesh, nvdiffrast 0.4.0, o-voxel, and the pinned
EasternJournalist/utils3d revision `9a4eb15e4021b67b12c460c7057d642626897ec8`.
CUDA extensions are built for architecture 12.1. The o-voxel build reuses Eigen
headers from CuMesh's cubvh dependency. Optional desktop OpenGL packages are not
needed by this CUDA pipeline.

Supporting weights are `facebook/dinov3-vitl16-pretrain-lvd1689m` and the sparse
structure decoder from `microsoft/TRELLIS-image-large`. These are downloaded from
ModelScope with checksum manifests. The generated white-background designs use
border-connected background removal instead of downloading a segmentation model.

`generate_meshes.py` includes two compatibility adaptations: PyTorch SDPA for
variable-length sparse attention, and the Transformers 5 DINOv3 encoder API.
The image encoder retains TRELLIS's original final feature normalization.
The tested TRELLIS.2 source revision is
`75fbf0183001ed9876c8dbb35de6b68552ee08bd`. Its local checkout must be writable
because the attention adaptation patches two source files idempotently.
Browser packaging requires `vendor/meshoptimizer-0.25/gltfpack`.

## Run and inspect

Copy these scripts from a checkout of My-Travel-Journey on Spark into the existing runtime:

```bash
base=/home/Developer/travel_journey_map
mkdir -p "$base/scripts"
cp journey-demo/nature_map/*.py journey-demo/nature_map/*.sh \
  journey-demo/nature_map/viewer.html "$base/scripts/"
tmux new-session -s sai-kung-rerun
```

Inside tmux, activate the isolated environment and run stages sequentially so
the large Qwen models release memory before TRELLIS starts:

```bash
source /home/Developer/miniforge3/etc/profile.d/conda.sh
conda activate travel_journey_map
cd /home/Developer/travel_journey_map
python -u scripts/understand_and_style.py extract
python -u scripts/understand_and_style.py understand
python -u scripts/understand_and_style.py style
bash scripts/run_geometry.sh
```

The source video must already exist at `runs/2026-09-22-demo/input/source.mp4`.
The launcher checks styled images and CUDA dependencies, generates meshes,
assembles Omniverse, packages browser assets, and installs `index.html`.
It targets the previously licensed Spark Omniverse installation. Detach with
Ctrl-B, then D; reconnect with `tmux attach -t sai-kung-rerun`.

Existing styled images and GLBs are reused. Analysis, USD, and browser exports
are replaced in the fixed run directory. To create a separate run, change the
`RUN` constants and launcher run path first. This README records the completed
sample; prompt/crop changes in the scripts apply only when an image is generated
again. The recorded traveler image was generated from the full source frame;
the current script crops the hiker for subsequent generation.

To serve the finished output on Spark, run in a separate tmux window (reuse the
existing server if port 8768 is already occupied):

```bash
python -m http.server 8768 --bind 127.0.0.1 \
  --directory /home/Developer/travel_journey_map/runs/2026-09-26-sai-kung-map/output
```

The private preview serves the run's `output/` directory on Spark port 8768:

```bash
ssh -f -N -o ExitOnForwardFailure=yes -L 8768:127.0.0.1:8768 dgx-spark
```

Open `http://127.0.0.1:8768/`. The browser uses pinned Three.js 0.180.0 modules.
Each viewer with SSH access creates this tunnel on their own computer, replacing
`dgx-spark` with their configured SSH alias. The localhost URL is private to that
computer, not a public sharing URL. Spark serves generated files; viewing does
not rerun inference. CDN access is needed for the browser libraries.

The run stores source frames under `input/`, actual model responses and
per-stage provenance under `analysis/`, and meshes, textures, memory thumbnails,
USD, the scene bundle, and browser files under `output/`. Weights, source media,
generated outputs, logs, and credentials are not included in this repository.

`check_viewer.cjs` validates actual asset loading, memory selection, pause/play,
scale/reset, camera rotation, lighting, and mobile overflow. Supply a Playwright
module path through `PLAYWRIGHT_MODULE` if it is not on Node's module search path.

Validation on 2026-09-26 passed in Chrome at desktop and mobile viewport sizes:
all three meshes loaded, all memory images loaded, pause froze animation time,
rotation/zoom/scale/reset and lighting worked, no page errors occurred, and the
mobile page had no horizontal overflow. Both the browser and the final Omniverse
RTX render were visually reviewed. The USD reload and boat time samples were
also verified.

Model, source-video, and dependency licenses remain with their respective owners.
