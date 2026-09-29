# My Travel Journey skills — release 1

Two repository-owned skills use **local Qwen on DGX Spark** to turn a travel
request and video into a reviewable evidence brief:

- [Trip intent understanding](trip-intent-understanding/SKILL.md)
- [Video evidence selection](video-evidence-selection/SKILL.md)

Copy the **whole `skills/` directory**, including `_shared/` and both schema
directories. Entry scripts work from any current directory. Harness-specific
installation and a StepFun coding-plan example are deferred.

## Execute on the existing Spark installation

```bash
skill_python=/home/Developer/miniforge3/envs/travel_journey_map/bin/python
export MEMGEN_QWEN_MODEL=/home/Developer/travel_journey_map/models/qwen3.6-27b

"$skill_python" skills/tools.py preflight
"$skill_python" skills/trip-intent-understanding/scripts/understand.py \
  --request-file /path/to/request.txt --out /path/to/new-intent-run
"$skill_python" skills/video-evidence-selection/scripts/select_evidence.py \
  --video /path/to/trip.mp4 --intent /path/to/new-intent-run/intent.json \
  --out /path/to/new-evidence-run
"$skill_python" skills/tools.py validate /path/to/new-evidence-run/evidence-brief.json \
  --video /path/to/trip.mp4
```

Read `review.md` and inspect `contact-sheet.jpg`, selected frames, and silent
clips. Requirements retain exact quotations from the request. Every proposed
moment has source timestamps, reference hashes, selection reasons, and limits.
Creative changes are kept separate from source evidence.

The helpers never invoke generation or publish outputs. A proposal is not a
confirmed choice. Missing or uncertain evidence stays visible in the brief.
Existing demos, source videos, model environments, and historical runs are not
modified. The skills do not load credentials or use external inference APIs.

Default selection budgets are 96 coarse and 24 refinement frames in batches of
6; budget options are documented in the selection skill. The default proposed
moment count is 3, with at most 3 references each. Source images remain private
run artifacts unless separately published.

## Validate and compare

```bash
python -m unittest discover -s skills/tests -v
"$skill_python" skills/tools.py evaluate \
  --video /path/to/trip.mp4 --cases skills/evals/evals.json \
  --out /path/to/new-comparison
```

CPU tests require FFmpeg/FFprobe and `skills/requirements.txt`; they use explicit
test doubles, never presented as local-Qwen results. GPU execution additionally
uses the existing compatible PyTorch, Transformers, Accelerate, and cached Qwen
checkpoint. Preflight reports those dependencies without changing them.

Evaluation keeps one model loaded, runs boat and hiking requests, and compares
adaptive with uniform candidate sampling using the same configured frame budget
and final selector. Raw prompts/replies and diagnostics are retained. Main moments must match an
essential scene/activity/relationship; unresolved subject references remain
uncertain even when visible counts match. Place requirements also remain
provisional: Release 1 does not independently
verify geography or structurally separate named locations from generic settings.
Visible setting descriptions remain available in the proposed moments. Automatic
coverage is model-assessed; factual errors and the actual meaning
of a scene require human inspection of the source. Do not infer generalization
or superiority from a single video.

See [the evaluation record](evals/RESULTS.md) for actual executed checks and
limitations. Scene-fidelity review, automatic repair, generation integration,
and a StepFun harness demonstration are later milestones.

## Browser application adapter

The separate [upload application](../upload-app/README.md) bundles these skills
as its shared Python dependency. Its video worker calls the existing entrypoint
implementation and preserves the evidence brief/catalog contract. Its photo
adapter reuses intent parsing, image inspection, selection, and source rechecking;
photo IDs and original/normalized hashes replace video timestamps. This does not
add photo input to the video-selection CLI. The application exports a separate
versioned proposal wrapper and records user approval without starting generation.

## Explicit source rechecks

When improving the checker, retain previous runs and use a new output directory:

```bash
"$skill_python" skills/tools.py recheck --video /path/to/trip.mp4 \
  --prior /path/to/completed-evidence-run --out /path/to/new-recheck
```

This validates original source/frame hashes and structured observations, then
runs local Qwen again on the shortlisted original images without prior captions.
It retains prior traces and refreshes the evidence descriptions and claim checks.
It does not silently resume a failed run. `evaluate --reuse-completed /path/to/old-evaluation`
explicitly rechecks completed matching cases; missing cases run normally. Sampling
settings and structured intent must match. Metrics label original plus recheck
cost; these staged timings are not fresh-run latency claims.
