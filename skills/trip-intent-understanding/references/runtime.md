# Runtime and output contract

The portable unit is the entire repository `skills/` directory. Both skills use
`_shared/memgen_skills`; moving only one entrypoint is unsupported. No harness
plugin, global installation, credential file, or hosted endpoint is required.

On the existing Spark installation:

- Python: `/home/Developer/miniforge3/envs/travel_journey_map/bin/python`
- Qwen: `/home/Developer/travel_journey_map/models/qwen3.6-27b`
- Tested runtime before this release: PyTorch 2.10.0+cu130, Transformers 5.17.0,
  Accelerate, NumPy, Pillow, and jsonschema. The skill preflight reports actual
  versions. The evidence skill additionally needs FFmpeg and FFprobe.

Model paths are configurable. The adapter uses local files, CUDA, bfloat16,
SDPA, deterministic decoding, and offline Hugging Face settings. There is no
external inference fallback. Large model loading can take several minutes.

Use an empty output directory. Existing artifacts are never silently resumed or
overwritten. A failed run retains its prompt, responses, validation error, and
`failure.json` where available; retry into a new directory.

`intent.json` is defined by [intent.schema.json](intent.schema.json): original
request, clarification text, proposed status, ordered requirements with stable
content-derived IDs, exact source quotations, priorities (3 essential, 2 supporting,
1 optional), visual-evidence flags, ambiguities, requested moment count, and model
provenance. Creative changes and exclusions are not positive source claims.

Intent IDs are stable for an unchanged structured requirement and preserved
through evidence selection. Rephrasing a requirement creates a new ID.

The inference schema constrains quotation choices to exact input sentences,
newline segments, or the whole request/context. Several requirements can reuse
one full sentence. This avoids ellipsis-spliced quotations while preserving the
original wording. Descriptions and priorities are still model interpretations;
an exact quotation does not prove that interpretation is correct.

No media is interpreted during this skill. A successful schema check establishes
structural validity and quote provenance, not semantic correctness. Review actual
requirements against the user's request.
