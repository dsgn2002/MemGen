# Release 1 validation record

Status: two skills implemented; local-Qwen execution for two intents, matched
sampling comparisons, artifact validation, and independent review completed.
Outputs remain proposals with unresolved requirements and documented descriptive
errors. No performance advantage or broad generalization is claimed.

## Completed local checks

- Both skill entrypoints pass the skill-creator structural validator.
- Twenty-one CPU tests pass: intent quotations, required companions versus optional scenery, creative changes, ambiguous identity,
  correction limits, run isolation, exclusions/duplicates, changed intent,
  whole-claim downgrades, strict JSON envelopes, unknown model frame IDs, compact-response index mapping, uncertain exclusions, moment overrides,
  real FFmpeg extraction/export/checksums, failed extraction handling, and a
  conservative place guard that rejects forged geographic support. CPU
  model calls are explicitly labeled test doubles.
- A separate fresh-output role-guard check confirms driver/companion ambiguity is
  downgraded, visible outfit descriptions are retained, and restoring invalid
  positive claims causes validation to fail. The private source-check response
  accepts a detail string as one unchanged list entry; public outputs remain
  strictly typed arrays.
- Spark preflight finds the local Qwen checkpoint, FFmpeg, CUDA, and the existing
  inference dependencies. It does not download models or replace the environment.

## Live comparison protocol

The acceptance evaluation uses the existing Sai Kung source, two highlight
requests, and adaptive versus uniform sampling. Both strategies receive 32
coarse plus 8 refinement frames per request for this bounded evaluation; normal
CLI defaults remain 96 plus 24. No timestamps are supplied to either strategy.

The source is 247.408617 seconds at 1280×720. SHA-256:
`efc60dc3aad3e4522fa5afce8e98d9974d9e456264a52cc256775a27c945c687`.
Inference uses the existing `qwen3.6-27b` checkpoint on Spark GB10, bfloat16,
SDPA, deterministic decoding, offline model loading, and three-frame batches.
The checkpoint's directory name identifies the installed model; no new model
training or fine-tuning was performed.

### Completed boat comparison (v6)

| Strategy | Evaluated frames | Proposed moments / references | Supported requirements | Redundant reference pairs | Accounted elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Adaptive | 40 | 1 / 1 | 0 / 2 | 0 | 1381.18 |
| Uniform | 40 | 3 / 3 | 0 / 2 | 0 | 1217.05 |

Redundancy uses selected-frame dHash distance ≤4. Coverage is the model's
requirement-level assessment after conservative export guards, not ground truth.
Both requirements remain uncertain because the request does not identify the
companions. The uniform run finds useful three-person boat evidence, but visible
headcount cannot establish that all three are the requested companions.

These are **staged runs**, reusing validated v4 observations with fresh v6
source checks: adaptive 1149.24 + 231.95 seconds; uniform 1070.70 + 146.35 seconds.
They include superseded checks and are not fresh-run latency measurements.
Hero timestamps: adaptive 219.294 s; uniform 57.9864, 220.3483, 235.8113 s.

Independent AI source review found zero unsupported **exported positive
requirement claims** in either brief. It flagged 3 adaptive and 5 uniform raw
Qwen self-check judgments as unsupported, and one incorrect exported descriptive
person count in the uniform brief. These are separate measures: conservative
requirement status does not make every description correct. See
[source review](SOURCE_REVIEW.md). Human-reviewed unsupported-claim metrics stay
null; an AI audit is not human ground truth.

### Fresh hiking comparison (v7)

The independent agent executed adaptive and uniform strategies from a fresh
directory with the same 32+8 budgets. Both completed. The raw outputs fail the
geography check: both place requirements were marked supported although the
frames do not establish “in Sai Kung.” These are retained as failed factual
results, not accepted coverage.

| Strategy | Evaluated frames | Proposed moments / references | Raw model coverage | Redundant reference pairs | Selection seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Adaptive | 40 | 3 / 7 | 3 / 3 | 1 | 1523.35 |
| Uniform | 40 | 2 / 2 | 3 / 3 | 0 | 1238.22 |

Hero timestamps: adaptive 84.3438, 95.5897, 190.6 s; uniform 96.644, 228.0798 s.
Fresh total execution was 3114.35 seconds, including 279.21 seconds of model
loading and the 70.48-second intent inference. Selection timings above exclude
the already-loaded model and separate intent stage. Peak PyTorch CUDA allocation
was 55,821,445,120 bytes; this is not total Spark unified-memory use.

The v8 exporter conservatively leaves every `kind=place` requirement uncertain,
including generic settings. Visible setting descriptions are retained. This
avoids inferring named geography from user wording without a location-name regex,
but understates support for generic places. A structured distinction and separate
location-verification mechanism remain future work. Only deterministic export
and validation changed. The independent agent exported existing verified v7
observations into fresh v8 directories with the same hero IDs, retained raw
traces, and original-brief checksums. This invoked no new inference; retained
v7 briefs remain the record of the factual failure.

### Corrected hiking handoff (v8)

| Strategy | Moments / references | Supported requirements | Weighted coverage | Redundant pairs | Original + export seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Adaptive | 3 / 7 | 1 / 3 | 0.25 | 1 | 1523.35 + 1.76 |
| Uniform | 2 / 2 | 1 / 3 | 0.25 | 0 | 1238.22 + 0.41 |

The visible-hiker requirement is supported; both place requirements are uncertain.
Independent AI review found zero unsupported exported positive requirement claims
in either corrected brief. Raw v7 self-checks still contain 14 adaptive and 3
uniform unsupported location-qualified frame links. These are not erased by the
export guard. A separate uniform description calls the water/cliff setting
“coastal”; the frame does not establish coast and may show reservoir context.
That descriptive uncertainty remains recorded in [source review](SOURCE_REVIEW.md).

The independent checker verified original source SHA, every selected frame and
clip hash, catalog/moment equality, silent clips, retained hero IDs, and unchanged
model counters. Both corrected briefs pass CLI validation against the original
video. See [independent execution record](INDEPENDENT_CHECK.md).

The fresh hiking run needed 7 adaptive and 3 uniform schema-correction calls for
scalar `visible_details` values in the initial frame response. Every correction
succeeded within the one-retry bound. Scalar handling in that initial response
is a future efficiency improvement; it was not changed or retested silently.

## Artifact locations

Paths below are relative to the repository workspace; generated media stays out
of the source bundle and public website.

- Boat: `tmp/skills-release1/final-v6/boat-companions/{intent,adaptive,uniform}/`.
- Fresh hiking run: `tmp/skills-release1/independent-v7/full-v7/`.
- Corrected hiking briefs: `tmp/skills-release1/independent-v7/export-v8/coastal-hike/{adaptive,uniform}/`.
- Reproducible export-only script: `tmp/skills-release1/independent-v7/export-v8-replay.py`.

Each evidence directory contains `evidence-brief.json`, `catalog.json`,
`review.md`, contact sheet, frames, silent clips, and model traces. Historical
attempts remain on Spark under `/home/Developer/travel_journey_map/runs/`.
The city website refresh used separate manually reviewed samples and existing
generation tools. It is not an automatic skills-to-generation integration test.

An initial real intent run split the group-on-boat relationship into fragments.
That run was stopped and retained. The prompt now requires self-contained
relationships. The current evaluation uses a compact private response schema
mapped back to the full public brief, reducing repeated JSON keys and IDs during
local decoding. The independent package check also exposed uncertain exclusions
outranking clear evidence; a targeted regression and conservative filtering were
added before the current comparison.

## Independent package check

A separate agent followed the packaged instructions from fresh output directories.
CPU preflight, CLI validation with original source hash, synthetic extraction and
export, and targeted reranking checks passed. All model calls in that check were
explicit test doubles. It found uncertainty promotion, missed exclusion checks,
an uncertainty-array mismatch, and misleading review-limit text. Those issues
were fixed and the agent rechecked them; no remaining material CPU-side finding
was reported. This does not validate real Qwen factual judgments.

Historical evaluation attempts are preserved on Spark. One stopped after
fragmented intent, another failed strict parsing of a JSON-fenced correction,
and a loading run was interrupted to include the independent review fixes.
The current run uses complete-claim shortlist verification and three-frame
batches. These attempts do not count as successful acceptance runs.

## Real-run findings before the final source recheck

The first completed 40-frame adaptive boat run passed artifact validation but
was not accepted as factual evidence of full requirement coverage. It reported
1.0 coverage while the intent still asked which three companions were meant,
and one visible person in the boat was operating it. Independent AI review
flagged both positive requirement-level support claims as unresolved. Street and
hiking appearance frames had also become unrelated main moments. The original
run remains preserved, including incorrect judgments.

The corrected export binds unresolved references to requirements, gates main
moments on essential scene requirements, and rechecks original images without
prior captions. Exclusion checks now use visibility states and positive content
labels. Fresh rechecks preserve prior observations and explicitly account for
staged runtime. The uniform coarse baseline independently found the brief
three-person boat shot that the 32-frame adaptive coarse sample missed. No
adaptive improvement is assumed.

The v6 hiking intent failed after the allowed correction because Qwen spliced
quotes with ellipses. The current package constrains quotes to an enum of exact
input sentences or the whole request/context. A targeted correction regression
and an independent CPU check passed. The fresh v7 hiking intent succeeded on its
first call. See SOURCE_REVIEW.md for the retained boat descriptive counting error
and hiking geographic failure.
