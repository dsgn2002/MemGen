# My Travel Journey — pipeline demo

Development runs on DGX Spark in a dedicated Conda environment named
`travel_journey_map`. Project data lives in `/home/Developer/travel_journey_map`.

## Current result: generated Sai Kung nature map

The latest workflow uses local **Qwen3.6-27B → Qwen-Image-Edit-2511 → TRELLIS.2
→ NVIDIA Omniverse** to create three textured meshes: terrain, traveler, and
boat. The interactive map has animated water and boat motion, three clickable
travel memories, rotation, zoom, scaling, and lighting controls. The traveler
is posed; the landscape is an artistic interpretation of the source video.

See [the nature map pipeline](nature_map/README.md) for the scripts, runtime,
validated result, rerun commands, and access instructions. The preview uses
port **8768**. The older depth-projection pipeline below uses port 8767.

## Earlier result: scenes 1–3 without StepFun

Run `runs/2026-09-22-scenes-123` contains the Sai Kung boat, coastal trail and Yi O
harvest moments. All geometry inference and Omniverse work ran on Spark. This
generation makes **zero StepFun calls** and never loads the credential file.
The earlier Stage 1 analysis below is historical and must not be rerun without
authorization for paid API use.

This result is **animated monocular depth projection**, not a complete 360° scan.
MoGe-2 estimates geometry from 12 frames per selected 1.5-second shot. The original
footage supplies textures and movement, including the travelers. Each scene has
32,400 vertices and 64,052 triangles; Omniverse Kit assembles the time-sampled
meshes and textures into USD and renders RTX previews. Hidden sides are absent,
wide rotations stretch the surface, and the people are not separately rigged.

The Spark-hosted viewer supports scene switching, recorded motion, drag rotation,
scroll/pinch zoom, scene scale, reset and a wireframe inspection mode. Its small
preview assets stream to the browser; the model and full output stay on Spark.
Open <http://127.0.0.1:8767/> while this SSH forward is active:

```bash
ssh -N -L 8767:127.0.0.1:8767 dgx-spark
```

If the preview server needs restarting, run on Spark:

```bash
python -m http.server 8767 --bind 127.0.0.1 \
  --directory /home/Developer/travel_journey_map/runs/2026-09-22-scenes-123/output
```

The output directory contains:

- `my-travel-journey.usdc`: editable animated USD with a `/World` **scene** variant
  for each moment. Choose that variant and the matching child camera.
- `my-travel-journey-omniverse.zip`: USD, relative frame textures, manifest and
  build report. Extract together to preserve the texture paths.
- Three `scene.glb` files: textured **still meshes**, read back from the actual
  USD stage. Video texture animation is provided by the browser and animated USD,
  not these GLB files.
- `manifest.json`, `build-report.json`, per-scene RTX previews, compressed depth
  frames and source-motion clips. The build report includes explicit exposure
  settings to reproduce photographic colors in Omniverse.

`reconstruct_selected.py` validates source and checkpoint SHA-256 checksums,
estimates frame geometry, stabilizes its ambiguous scale, and writes positive
finite depth grids. `build_reconstruction.py` assembles these in Omniverse and
checks USD/GLB reloads, animation samples, non-flat geometry, and nonblank RTX
captures. `reconstruction.html` displays the same geometry in Three.js.
`check_reconstruction.cjs` exercises all scenes, motion, rotate/zoom/scale,
wireframe, mobile layout and download availability in Chrome.

The installed reconstruction stack adds PyTorch 2.10.0+cu130, torchvision
0.25.0+cu130, OpenCV-headless 4.13.0.92, scipy 1.18.1, MoGe's v2 model code, and
the pinned `utils3d_moge` dependency. Existing compatible GPU packages were
copied into the isolated Conda environment, not linked to another environment;
the Spark's `runtime-copy-manifest.json` records this. `environment.yml` describes
the base pipeline, not this full GPU stack. Model weights:
[`Ruicheng/moge-2-vits-normal`](https://huggingface.co/Ruicheng/moge-2-vits-normal),
SHA-256 `79a16621928c2bf0ed04659218c55c01075e950507f40bb3332fb4c873d3e1dc`.
No image generation API is needed. See [MoGe](https://github.com/microsoft/MoGe).

## Activate on the Spark

```bash
ssh dgx-spark
source /home/Developer/miniforge3/etc/profile.d/conda.sh
conda activate travel_journey_map
cd /home/Developer/travel_journey_map
```

The interpreter is
`/home/Developer/miniforge3/envs/travel_journey_map/bin/python`.
Python dependencies, including Omniverse Kit, are installed in this environment.
The NVIDIA driver and `/usr/bin/ffmpeg` are shared host dependencies.
The earlier project `.venv` is unused; use Conda for subsequent development.

To recreate the environment on a compatible Linux host:

```bash
conda env create --file environment.yml
```

Omniverse Kit is pinned to the ARM64 package installed for the Spark. Its first
launch requires acceptance of the
[NVIDIA Omniverse license](https://docs.omniverse.nvidia.com/platform/latest/common/NVIDIA_Omniverse_License_Agreement.html).
Installing the package does not establish that the renderer has been tested.

## Stage 1: review and scene selection

The current user flow is **understand → summarize and suggest → user chooses →
generate the selected scenes**. The review shows four source-backed suggestions,
with visible travelers and natural scenery, instead of immediately creating a
primitive world. The first reviewed scene will be the visual quality gate for
the eventual realistic generation pipeline.

`review_journey.py` has three separate operations:

```bash
# On the Spark, in the dedicated travel_journey_map Conda environment:
python scripts/review_journey.py prepare \
  --source-run runs/2026-09-22-demo --run runs/2026-09-22-review
python scripts/review_journey.py analyze --run runs/2026-09-22-review \
  --env "$HOME/.config/my-travel-journey/stepfun.env"
python scripts/review_journey.py render --run runs/2026-09-22-review \
  --editorial scripts/review_copy_edits.json
python scripts/serve_review.py --run runs/2026-09-22-review --port 8766
```

The preparation step checks the original video hash, extracts timestamped source
frames and silent short clips, and preserves the previous video observations
and ending check. The demo's four candidates are curated in
`review_candidates.json`; arbitrary-video automatic shot selection remains
future work. The analysis step calls actual `step-5-preview` using those
observations and seven source frames. It produces `analysis/journey_review.json`
and records the prompt, response model, usage, and endpoint.

The optional copy edits correct source-specific details and simplify the visible
wording. They are tied to this video's hash and preserved alongside the unedited
model output, so they must not be reused for another video. The review labels
this source check in its provenance details.

The rendering step writes a portable `output/` folder with the readable summary,
scene cards, clips, and `review.json`. Serving that folder with `serve_review.py`
adds the selection endpoint. Open `http://127.0.0.1:8766/` on the server's machine;
for a Spark-hosted server, forward port 8766 over SSH. On the Mac, use:

```bash
python3 journey-demo/serve_review.py \
  --run journey-demo/runs/2026-09-22-review --port 8766
```

**Save scene for generation** writes `selection.json` at the run root, retaining
the source hash, exact frame timestamps, reference images, chosen proposals,
optional notes, and planned rotation/zoom/scale controls. Reloading restores the
saved choices, and the brief is downloadable. Checkbox changes alone are not saved;
no candidate is automatically confirmed. The local endpoint checks review
versions and candidate IDs, and accepts same-origin JSON requests only.

The review server does **not** launch a 3D job. The reconstruction stage above
reads this confirmed brief and builds depth surfaces in Omniverse, with unseen
sides left unmodeled. The old primitive builder below remains a historical
visual prototype.

## Original Step 5 video understanding

The shared credential file is
`/home/Developer/.config/my-travel-journey/stepfun.env`. It defines
`STEPFUN_API_KEY`, `STEPFUN_MODEL`, and `STEPFUN_BASE_URL`. The client also accepts
the aliases `STEP_API_KEY`, `STEP_MODEL`, and `STEP_API_BASE`.
Keep this file private and outside version control.

The user selected the Step Plan subscription endpoint:
`https://api.stepfun.com/step_plan/v1`. The launcher sets this endpoint for the
project without changing the shared credential file. The international `.ai`
endpoint rejected this key. Earlier pay-as-you-go endpoint attempts did not
produce usable observations and are retained only as diagnostic records.

Each run uses an `input/source.json` provenance record and an
`input/analysis.mp4` video copy sampled at 3 fps, without audio. After those
inputs have been transferred, run:

```bash
bash scripts/run_step5.sh
```

The launcher now defaults to observations only, so it does not bypass the review
stage. The historical demo has two actual model outputs in its `analysis` directory:

1. `journey_observations.json`: timestamped visual observations and selected stops.
2. `world_spec.json`: a proposed miniature layout with concrete geometry parts,
   colors, traveler figures, captions, and source video ranges.

Strict JSON schemas reject empty or incomplete model outputs. Prompt text,
response metadata, usage, and validation results are retained for inspection.
The world specification describes stylized approximations, not a
measured reconstruction. The analysis script itself does not generate meshes.

## Historical stylized demo: build and view

After Step 5 produces a validated design, run the following on the Spark. The
EULA setting reflects the user's explicit acceptance of NVIDIA's license for
this project.

```bash
OMNI_KIT_ACCEPT_EULA=yes python scripts/build_world.py \
  --run /home/Developer/travel_journey_map/runs/2026-09-22-demo --render
python scripts/make_viewer.py \
  --run /home/Developer/travel_journey_map/runs/2026-09-22-demo
```

The builder creates the scene inside Omniverse Kit, saves an editable `.usda`,
reads the USD geometry back, and exports a `.glb`. It checks primitive dimensions,
finite coordinates, and USD/GLB reloads. `--render` also captures the RTX viewport.
The separate `renderer-smoke-test` run contains synthetic test geometry and is
never represented as Step 5 output or a travel reconstruction.

`output/viewer.html` embeds the GLB and the pipeline JSON. It supports drag
rotation, scroll/pinch zoom, a 0.5–2× geometry size slider, and GLB downloads that
preserve the selected scale. It also supports stop selection, a guided tour,
linked YouTube moments, and inspection of each model output, including the
separate ending check that supplements the first pass's sampling coverage.
It requires internet for the pinned model-viewer library and YouTube playback.
Serve the output directory over localhost HTTP to use the download links.
