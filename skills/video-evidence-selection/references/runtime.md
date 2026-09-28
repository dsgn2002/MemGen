# Execution and evidence contracts

Use the complete bundle, including `_shared/`, both schema directories, and
`tools.py`. See the [shared runtime description](../../trip-intent-understanding/references/runtime.md).
The skill reads a local source and writes a new output directory; it never edits
the source, installs models, loads API credentials, or calls a hosted model.

## Discovery and analysis

FFmpeg detects shot changes at 2 fps on a small image stream. Adaptive sampling
allocates roughly two thirds of its coarse budget to duration-wide coverage and
the remainder to shot interiors. Uniform mode uses duration-wide sampling alone.
Blur/exposure and perceptual hashes are measured on extracted frames. Every
candidate goes through actual local Qwen visual analysis; near-duplicate hashing
does not copy model observations between images.

Adaptive refinement inspects nearby frames in promising shots and spends unused
budget on additional temporal coverage. Uniform refinement continues sampling
across the duration. The same final selector is used in both modes. Very short
videos or duplicate timestamps may use fewer than the configured budget; actual
counts are recorded. The output may contain fewer moments than requested when
supporting evidence is insufficient.

The selector rechecks complete claims on shortlisted original frames in at most
two rounds, reranking after downgrades. Unchecked replacements are not exported.
This reuses sampled images and does not increase the unique-frame budget. Actual
model calls and elapsed time include these checks. Initial observations, changed
judgments, and verified observations are retained under `analysis/`. This is
model self-checking, not independent factual ground truth. Each source recheck
produces fresh people, setting and preservation details without seeing earlier
captions. Excluded content is checked as visible/uncertain/not_visible, with
negated instruction prefixes removed from visual claim descriptions.

Main moments must match an essential subject, scene, activity or relationship;
appearance-only evidence cannot create an unrelated main moment. A source image
cannot resolve an ambiguous personal reference: matching unresolved phrases in
requirements are kept uncertain in the exported brief. When a subject or
relationship is ambiguous, all appearance requirements are conservatively kept
uncertain too; explicit subject IDs are a future refinement. This can reduce
reported coverage for unrelated appearance details, rather than inventing a
cross-frame identity binding.

Descriptions mentioning a driver, guide, operator or other worker role also keep
requested companion relationships and appearance uncertain. A visible person
count alone cannot establish group membership. This conservative text guard can
overflag a legitimate companion with such a role; the proposal requires review.

Every `kind=place` requirement is also kept uncertain at export, and validation
rejects positive place support. Release 1 has no independent location confirmation
or structured separation of generic settings from named geographic qualifiers.
This intentionally understates support for generic place requirements. Visible
coasts, trails, buildings and signs remain in observations for review; a matching
description is not independent proof of the requested location. Raw positive
model judgments are retained in analysis, so this guard does not hide failures.

## Outputs

- `evidence-brief.json`: source hash/metadata, original intent, proposed moments,
  requirement support, unresolved requirements, sampling, metrics, provenance.
- `catalog.json`: the same moment records, preserving existing `id`, `location`,
  `hero_timestamp_s`, `reference_timestamps_s`, and `clip_range_s` field names.
  Location stays null unless a future verified location step is added.
- `assets/`: original sampled JPGs and selected silent MP4 clips. References use
  paths relative to the output directory; timestamps are requested source seek
  positions, decoded to the nearest available frame by FFmpeg.
- `contact-sheet.jpg`, `review.md`: human inspection artifacts.
- `analysis/`: candidates, observations, prompts, raw replies, correction errors.

See [evidence-brief.schema.json](evidence-brief.schema.json). Runtime validation
also checks temporal bounds, asset paths, unique IDs, reference relationships,
and checksums. Reports remain `proposed`, `user_confirmed=false`, and
`generation_started=false`. There is no automatic call into reconstruction.

Model responses may have one complete JSON code fence; its contents must still
pass the full schema. Extra prose is rejected. One correction is allowed.
The private source-check wire schema accepts preservation details as a string
or an array of strings. A scalar becomes one unchanged array entry in the public
output; it is never split or interpreted. All other types are rejected.

## Evaluation

```bash
python /path/to/skills/tools.py evaluate \
  --video /path/to/trip.mp4 --cases /path/to/skills/evals/evals.json \
  --model-path /path/to/qwen-checkpoint --out /path/to/new-evaluation
```

This keeps one model loaded and runs two requests, each with adaptive and uniform
sampling under matched configured frame budgets. `comparison.json` contains
actual counts, timestamps, model-assessed coverage, duplicate pairs, and timing.
Cold model load is separate in model metadata. PyTorch allocated CUDA memory is
not total DGX unified-memory usage. Schema retries can change actual call counts.

Human review must assess unsupported visual claims and requirement coverage
against the original footage. The automatic report leaves human factual-review
metrics null until reviewed; model self-assessment is not independent ground truth.
Results on one video do not establish broad generalization. `--skip-baseline`
is only a smoke test and does not satisfy the comparison acceptance criterion.

## Explicit rechecks

`tools.py recheck --video /path/to/source.mp4 --prior /path/to/completed-run
--out /path/to/new-run` validates source/frame hashes and structured observations,
checks the complete candidate manifests/counts and observation digest when
available, then runs local Qwen on shortlisted original images again. New
outputs record the observations digest. Legacy runs without that digest are
explicitly labeled, and still require exact candidate-manifest agreement. Original analysis and
brief are retained as `prior-analysis/` and `prior-evidence-brief.json`. There is
no silent resume or substitution for a failed inference call. The output records
old plus recheck elapsed time, so it must not be advertised as fresh-run latency.
Evaluation can explicitly reuse completed matching runs with `--reuse-completed`;
it rejects mismatched intents or configured sampling settings.
