# Application release checks

- 25 shared skill tests: structured intent, source linkage, evidence selection,
  bounded corrections and recovery of real source-linked observations.
- 17 application tests: upload/resume, media checks, owner isolation, approval
  binding, generation queue guards, changed-source rejection, cancellation and source-bound presentation edits.
- Four upload-client checks: adaptive transfer, slow links, lost acknowledgements
  and altered reselected files.
- Live local-Qwen upload analysis produced three proposed moments and style
  suggestions. All three preview clips played in Chrome without page errors.
- Source positions and preview durations are shown separately; selected duration
  merges overlapping intervals and preserves saved choices.

CPU tests use explicit test doubles; production has no fake-inference mode.
Live DGX Spark execution generated two approved moments using local Qwen Image
Edit and TRELLIS.2. Generation took 14 minutes 14 seconds, including cold model
loading: styling 10 minutes 42 seconds, meshes 3 minutes 30 seconds, and packaging
about one second. The resulting meshes contain approximately 56,500 and 57,300
triangles; browser downloads are below 1 MB each.

The first analysis attempt through generation completion took 75 minutes
24 seconds, including earlier failed attempts, fixes, implementation and user
review time. This is a development-session measurement, not an inference benchmark.

Chrome verification passed for both textured meshes, source/design images,
atmosphere switching, camera reset and a 390-pixel phone layout with no horizontal
overflow. Browser checks inspect material textures and console failures as well
as geometry and page errors. Visual screenshots confirmed full-color surfaces.
Private run identifiers, uploaded sources and local diagnostic reports are excluded
from this public release record.

## Curated geometry refinement

The restaurant presentation uses four generic CC0 Quaternius characters (two
male and two female), each with its own skeletal Idle animation. The lantern
presentation uses ten separate round/fish lanterns with gentle sway. These are
manual scene assemblies following user feedback, not additional model inference
or automatic repair for arbitrary footage. Their source-bound manifests are
private; the original generated meshes and inference timing remain unchanged.

Local and deployed Chrome checks passed for both assemblies, four skeletal idle
animations, ten swaying lanterns, pause/resume, original/refined switching,
atmosphere controls, and phone layout without overflow or page errors.
Screenshots of the deployed scenes were visually inspected.
