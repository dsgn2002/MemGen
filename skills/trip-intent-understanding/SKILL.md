---
name: trip-intent-understanding
description: Turn a traveler's requested video highlights into explicit, source-quoted requirements using local Qwen. Use before choosing video moments, or when a user changes which people, activities, places, or appearance details matter.
license: MIT
---

# Trip intent understanding

Produce a proposed `intent.json` that expresses what the user wants preserved.
This skill interprets instructions; it has not observed the video and must not
turn preferences into claims about its contents.

## Runtime

Distribute the complete `skills/` bundle: this entrypoint depends on sibling
`_shared/`, `tools.py`, and the checked-in schemas. See
[runtime and output contracts](references/runtime.md). Use the existing Spark
Python environment and explicitly configured local Qwen checkpoint. Run preflight
before inference; do not install or replace the CUDA runtime as a recovery step.

```bash
python /path/to/skills/tools.py preflight --model-path /path/to/qwen-checkpoint
python /path/to/skills/trip-intent-understanding/scripts/understand.py \
  --request-file /path/to/request.txt \
  --model-path /path/to/qwen-checkpoint --out /path/to/new-intent-run
```

Optional `--context-file` supplies the user's clarifications as plain text.
`MEMGEN_QWEN_MODEL` can replace the repeated `--model-path` argument.

## Decisions that matter

- Preserve requested counts and relationships: three companions **together on
  the boat** is more specific than “people” and “boat.”
- Separate required details, supporting preferences, exclusions, and creative
  changes. “Add sunset lighting” does not require evidence of a filmed sunset.
  “Keep a natural look” is also a rendering preference; it is not a visible
  attribute of a person. Appearance evidence describes concrete source features
  such as clothing or hair color.
- Retain the original request and exact source quotations. Do not invent names,
  locations, appearances, identities, or observed facts.
- Record unclear references such as “us” for resolution against candidate frames.
  Ask a clarification only when it materially changes selection and existing
  context does not resolve it. The skill can proceed with a clearly labeled
  ambiguity; it cannot declare that strangers in the footage are the user.
- The local model creates the requirements. Review its structured output for
  faithful interpretation; make corrections through the user's clarification
  context and a fresh run, preserving the original output and trace.

## Handoff

Validate with `python /path/to/skills/tools.py validate /run/intent.json`.
Present the priorities and unresolved questions in plain language. Pass the
validated file to `video-evidence-selection` when video selection is requested.
This skill does not call generation, publish media, or mark a user choice confirmed.

Invalid JSON or a rejected structured interpretation receives one automatic correction attempt. If validation still
fails, report the diagnostics directory. Do not substitute a guessed brief or
represent the run as successful.
