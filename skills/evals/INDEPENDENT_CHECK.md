# Independent Release 1 execution and source audit

Date: 2026-09-27
Reviewer: independent coding agent
Status: completed with retained limitations

This record covers the independent fresh live-Qwen coastal-hike evaluation and
the deterministic export-only replay that applied the final conservative place
guard. It is an AI source audit, not human ground truth.

## Source and request

- Source video: `journey-demo/runs/2026-09-22-demo/input/source.mp4`
- Source SHA-256:
  `efc60dc3aad3e4522fa5afce8e98d9974d9e456264a52cc256775a27c945c687`
- Duration: 247.408617 seconds
- Resolution: 1280×720
- Request: “Highlight the coastal hiking trail and rocky coastline in Sai
  Kung. Include the visible hiker when supported. Avoid farm and indoor
  scenes.”
- Budgets: 32 coarse frames plus 8 refinement frames per strategy, batches of
  three, adaptive and uniform.

No timestamps or target answers were supplied to the selector.

## Fresh v7 live-Qwen execution

The independent run used the deployed v7 bundle on Spark:

- Bundle:
  `/home/Developer/travel_journey_map/skill-releases/2026-09-27-release1-v7/skills`
- Model:
  `/home/Developer/travel_journey_map/models/qwen3.6-27b`
- Remote output:
  `/home/Developer/travel_journey_map/runs/2026-09-27-skills-hike-independent-v7`
- Preserved local copy:
  `tmp/skills-release1/independent-v7/full-v7`

The command was invoked once:

```bash
ssh -o BatchMode=yes dgx-spark \
  '/home/Developer/miniforge3/envs/travel_journey_map/bin/python -u \
  /home/Developer/travel_journey_map/skill-releases/2026-09-27-release1-v7/skills/tools.py evaluate \
  --video /home/Developer/travel_journey_map/runs/2026-09-22-demo/input/source.mp4 \
  --cases /home/Developer/travel_journey_map/runs/2026-09-27-skills-hike-independent-v7-cases.json \
  --model-path /home/Developer/travel_journey_map/models/qwen3.6-27b \
  --out /home/Developer/travel_journey_map/runs/2026-09-27-skills-hike-independent-v7 \
  --coarse-budget 32 --refinement-budget 8 --batch-size 3'
```

The intent call succeeded on its first attempt with exact full-sentence source
quotes and no ambiguity. Qwen loaded once in 279.2050 seconds. The complete
evaluation took 3114.3451 seconds and produced both strategies without a final
inference failure.

| Strategy | Evaluated frames | Moments / references | Positive requirements reported supported | Duplicate reference pairs | Selection elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Adaptive | 40 | 3 / 7 | 3 / 3 | 1 | 1523.3511 |
| Uniform | 40 | 2 / 2 | 3 / 3 | 0 | 1238.2245 |

Adaptive hero timestamps were 84.3438, 95.5897, and 190.6000 seconds. Uniform
hero timestamps were 96.6440 and 228.0798 seconds.

### Why v7 did not pass the factual gate

Both place requirements include the geographic qualifier “in Sai Kung.” The
source frames do not independently establish that location. Adaptive frame
`frame-0026` at 192.0 seconds visibly contains a “Welcome to Lai Chi Wo” sign,
which makes request-derived geographic attribution especially unsafe.

Nevertheless, v7 exported both exact place requirements as supported. This was
two unsupported aggregate requirement claims in each strategy, corresponding
to 14 unsupported adaptive frame-to-requirement links and three unsupported
uniform links. The figures count exact complete claims: each link includes a
geographic qualifier that the image cannot prove. v7 is preserved as the
failed factual-gate result and was not rewritten.

## v8 deterministic export-only replay

Only deterministic export and validation changed after v7. The reviewer did
not start another GPU process or make another model call. The v8 replay used
the preserved v7 `analysis/verified-observations.json`, the same hero frame IDs,
the original source images and hashes, and the final conservative guard that
keeps every `kind=place` requirement provisional.

- Replay script:
  `tmp/skills-release1/independent-v7/export-v8-replay.py`
- Output root:
  `tmp/skills-release1/independent-v7/export-v8`

The exact replay command was:

```bash
PYTHONPATH="$PWD/tmp/skill-test-deps" python3 \
  tmp/skills-release1/independent-v7/export-v8-replay.py \
  --prior-root tmp/skills-release1/independent-v7/full-v7 \
  --out-root tmp/skills-release1/independent-v7/export-v8 \
  --video journey-demo/runs/2026-09-22-demo/input/source.mp4 \
  --skills skills
```

The replay records the prior brief and verified-observation digests, identifies
itself as export-only, preserves the original model metadata and inference
counters, and separates prior inference time from export time.

| Strategy | Moments / references | Supported positive requirements | Weighted coverage | Duplicate pairs | Prior seconds | Export seconds | Accounted seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Adaptive | 3 / 7 | 1 / 3 | 0.25 | 1 | 1523.3511 | 1.7578 | 1525.1089 |
| Uniform | 2 / 2 | 1 / 3 | 0.25 | 0 | 1238.2245 | 0.4112 | 1238.6356 |

For both strategies, “Visible hiker” remains supported and the two place
requirements are uncertain. Farm and indoor requirements remain exclusions.
The uniform brief correctly reports its two-of-three moment shortfall using the
generic unresolved-requirements explanation.

## Artifact validation

The reviewer ran the packaged validator against each v8 brief and the original
source:

```bash
PYTHONPATH="$PWD/tmp/skill-test-deps" python3 skills/tools.py validate \
  tmp/skills-release1/independent-v7/export-v8/coastal-hike/adaptive/evidence-brief.json \
  --video journey-demo/runs/2026-09-22-demo/input/source.mp4

PYTHONPATH="$PWD/tmp/skill-test-deps" python3 skills/tools.py validate \
  tmp/skills-release1/independent-v7/export-v8/coastal-hike/uniform/evidence-brief.json \
  --video journey-demo/runs/2026-09-22-demo/input/source.mp4
```

Both returned `VALID`. Additional inspection confirmed:

- source SHA-256 matches the recorded source;
- each `catalog.json` equals the brief's exported `moments` array;
- selected source-image and silent-clip hashes match their records;
- the adaptive hero frame IDs remain `frame-0010`, `frame-0012`, and
  `frame-0036`;
- the uniform hero frame IDs remain `frame-0012` and `frame-0029`;
- FFprobe reports a video stream and no audio stream for every exported clip;
- original model metadata, call counts, inference seconds, and generated-token
  counts are unchanged from v7.

The preserved prior-brief SHA-256 values are:

- Adaptive:
  `b38704c8fdf14d5e380ea63d05eb023756af921ba91a1ee0f8eb61cccd464353`
- Uniform:
  `7ba81bbc5919caa1578a199201acc09c19f0ea47e602ba66f30995f95b1d1978`

The preserved verified-observation SHA-256 values are:

- Adaptive:
  `79e00be19961b5ae92e49be646eafb6cf6fde8e1578102f61b38e4a35fb33f14`
- Uniform:
  `ab41b5a147ec46020bd68903d071e7410725525587493b449369b378a57ab701`

## Independent source findings

Original-resolution review found all exported positive hiker-support claims
defensible:

- Adaptive: seven of seven selected references show visible people in hiking or
  trail context. The three-person boardwalk views contain a partly occluded
  third walker; the original images resolve the thumbnail-level uncertainty.
- Uniform: `frame-0029` clearly shows a person with a backpack walking on a
  wooded path.

Therefore the v8 briefs contain zero unsupported exported positive requirement
claims in either strategy. The v7 raw source rechecks retain the 14 adaptive and
three uniform unsupported exact-place judgments described above; v8 exposes
those place links as uncertain rather than supported.

One separate public descriptive overclaim remains in the uniform brief:
`frame-0012` at 96.644 seconds says “Coastal cliff overlooking water.” The
image shows cliff and water with a MacLehose Trail overlay, but does not prove
that the water is coastal and appears to be reservoir context. The v8 place
guard prevents this text from becoming positive place-requirement support, but
the descriptive wording still requires human review.

No selected v8 frame visibly contains a farm or indoor scene. Identities,
personal relationships, exact geography, hidden appearance details, and
recoverable 3D geometry remain unverified.

## Inference diagnostics and limits

The fresh v7 run retained ten successful correction events:

- Adaptive: seven first-attempt schema errors.
- Uniform: three first-attempt schema errors.

All ten were `visible_details` string-versus-array mismatches during initial
coarse or refinement inspection. Every allowed retry succeeded; there was no
terminal observation or source-check failure. Scalar compatibility for the
initial frame wire is a possible future efficiency improvement, but is not a
blocker for this completed run.

Coverage values are model assessments over one source video and do not measure
broad generalization. The v8 timings are staged v7 inference plus deterministic
export, not fresh v8 inference latency. Human factual-review metrics remain
null, and this independent AI audit does not replace human review.
