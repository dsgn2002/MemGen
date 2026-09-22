# My Travel Journey — realistic reconstruction revision

The user rejected the primitive diorama on 22 September 2026. It does not meet
the requested visual quality or preserve the traveler's appearance. Passing
rotation, scaling, and export tests does not establish visual acceptance.

## Why the first result failed

The design prompt explicitly requested low-poly scenery and generic faces, and
the compiler only supported boxes, spheres, cylinders, and cones. Source images
were not used as textures or as input to geometry reconstruction. Omniverse
rendered that simplified scene correctly; the missing stage was realistic asset
reconstruction/generation. More primitives or a different light setup cannot
recover the discarded detail.

## Revised pipeline

1. **Step 5: summarize and suggest; user selects.** Present a readable journey
   summary and a few specific scenes with actual source frames, short video
   previews, visible people, and proposed natural surroundings. Explain which
   details are visible and which would need completion. Let the user choose a
   first scene and add optional preferences; save an explicit selection brief
   before generation. A recommended scene is not a user selection.

   Then inspect the selected shot's coverage. Split the video into continuous shots. Select
   sharp frames of the traveler, face/clothing/pose, and scenery. Preserve source
   timestamps and group only views that actually show the same scene. Do not
   infer the person's name or other sensitive identity information.
2. **Separate the traveler and environment.** Segment the person and retain
   texture references. Mask moving people when reconstructing static scenery.
   A moving person must not be fused into a static landscape scan.
3. **Reconstruct or generate textured 3D assets.** For sufficiently overlapping
   views, estimate cameras and reconstruct the environment using a neural
   reconstruction pipeline. For sparse views, evaluate an image-conditioned
   textured mesh generator and label unseen surfaces as generated. Treat the
   traveler as a separate asset with recognizable visible appearance; a generic
   mannequin is not acceptable.
4. **Omniverse: assemble and render.** Import the reconstructed USD particle
   field and/or textured meshes, place the traveler, set realistic illumination,
   and render comparison views. Step 5's layout becomes an assembly manifest
   referencing these real assets, rather than a list of primitive substitutes.
5. **Interactive delivery.** Preserve rotation, zoom, scale, and linked memories.
   Meshes can be delivered as GLB. Gaussian splats need a compatible splat viewer
   or streaming; do not claim that ordinary GLB preserves a Gaussian scene.

## First quality gate

Produce one scene with a clearly visible traveler before expanding to all three
journey stops. Compare a rendered view with its actual source frame. Check
visible face/clothing, body proportions, terrain silhouette, vegetation detail,
photographic textures, ground contact, and plausible lighting. Check side views
separately. A still photograph on a plane is not a fully reconstructed person.

Do not mark the revised souvenir complete until this visual check passes.
Unseen sides cannot be recovered exactly from an edited vlog. Whether plausible
AI completion is acceptable determines the reconstruction route and viewing
limits; the user has been asked this preference.

## Current evidence and readiness

**Updated result:** scenes 1–3 now have animated, textured depth surfaces in
`/home/Developer/travel_journey_map/runs/2026-09-22-scenes-123` on Spark.
MoGe-2 runs locally, with no StepFun calls during generation; NVIDIA Omniverse
Kit builds the animated USD and RTX previews. The browser supports rotation,
zoom, scale and geometry inspection. Original people and natural scenery are
visible in the source-facing views. This meets the later request to try a
projection-based souvenir; it does not implement the separate complete human
assets or a complete multi-view environment described in the longer-term plan.
Hidden sides, wide-angle quality and separate character rigs remain limitations.
The implementation and controls are documented in `journey-demo/README.md`.

- Stage 1 is implemented in `journey-demo/review_journey.py`, `review.html`,
  and `serve_review.py`. Its review run is `2026-09-22-review`. Step 5 uses the
  prior observations and ending check plus seven exact source frames to write
  four proposals. The candidate timestamps were curated from this film; this
  is not yet an automatic shot-selection system for arbitrary videos.
- A user click on **Save scene for generation** writes `selection.json` with
  source provenance, selected scene, image hashes/timestamps, user notes, and
  rotation/zoom/scale requirements. It does not launch generation. Hidden-side
  completion is recorded as an unresolved preference, not silently approved.
- The original 247.41-second film is available locally and on the Spark; its
  transferred checksum is verified.
- Source frames were extracted into the separate
  `journey-demo/runs/2026-09-22-realism/references/` run. They are references,
  not a new 3D result.
- Step 5 and Omniverse Kit work in the isolated `travel_journey_map` environment.
- The isolated environment now has GPU PyTorch, OpenCV, scipy and MoGe-2. Geometry
  inference and Omniverse assembly/rendering have run successfully. COLMAP and a
  full multi-view reconstruction remain outside this projection prototype.
- The film contains short edited shots, moving people, boats/water, and changing
  viewpoints. Multi-view coverage must be checked per shot; a five-minute total
  runtime does not imply a complete scan of any person or location.

## Candidate implementations, not validated claims

- NVIDIA's [mono-camera reconstruction workflow](https://docs.nvidia.com/nurec/robotics/neural_reconstruction_mono.html)
  uses COLMAP and 3DGUT. It recommends steady imagery, multiple viewpoints, and
  overlapping capture. This is a candidate for suitable continuous scene shots.
- Omniverse [supports Gaussian particle fields](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/particle-fields.html),
  including conversion from splat PLY to USD. Rendering support does not itself
  reconstruct the footage.
- [TRELLIS.2](https://github.com/microsoft/TRELLIS.2) generates textured assets
  from images. Its documented hardware validation is A100/H100; GB10/ARM64
  compatibility must be established before promising it as the Spark solution.
  Generated human likeness and natural-scene quality need direct evaluation.
