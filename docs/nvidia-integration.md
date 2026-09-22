# NVIDIA integration plan

Status: Omniverse Kit assembly, RTX rendering and USD/GLB export are validated on
DGX Spark. The broader agent tooling below remains a set of researched candidates.

The current product design is [My Travel Journey](my-travel-journey-plan.md).
The working demo reuses the saved Step 5 journey review, estimates selected
frames' geometry locally with MoGe-2, and assembles it in Omniverse without new
StepFun API calls. See the [implemented pipeline](../journey-demo/README.md).
The first-agent demonstration below records the earlier mesh-personalization
milestone; the broader multi-tool architecture remains planned.

## Existing tools to reuse

| Component | Proposed role | Official source |
| --- | --- | --- |
| NVIDIA Agent Skills catalog | Discover relevant portable instructions for the selected NVIDIA products. Skills guide an agent; they are not inference endpoints or a runtime. | https://github.com/NVIDIA/skills |
| DGX Spark Hermes playbook | Candidate quickest route to a local tool-using agent and local vLLM serving. Hermes is an upstream project documented in NVIDIA's official playbooks, not an NVIDIA-authored agent. | https://github.com/NVIDIA/dgx-spark-playbooks/tree/main/nvidia/hermes-agent |
| NVIDIA NeMo Agent Toolkit | Alternative orchestration/instrumentation approach for explicit tools, traces and evaluation. Choose one core runtime after checking event requirements. | https://github.com/NVIDIA/NeMo-Agent-Toolkit |
| NeMo Relay skills | Candidate guidance for instrumentation and observability if Relay is chosen. Catalog entries include nemo-relay-get-started and nemo-relay-plugin-observability. | https://github.com/NVIDIA/skills |
| NVIDIA DGX Spark | Local model inference and artifact processing on ARM64/GB10. GPU execution and model throughput must be measured separately from CPU mesh processing. | https://github.com/NVIDIA/dgx-spark-playbooks |

No NVIDIA-specific skills or tools were installed into MemGen during repository setup. Avoid installing the full skill catalog; select only skills relevant to the actual implementation. Model selection remains provisional: use the current official Spark serving recipes and benchmark image input, tool calling, latency and memory before committing to a model.

## First useful agent demonstration

Visitor request: "Make Alex a campus explorer souvenir with a gold base."

Agent selects a catalog asset, calls customization, checks name fidelity and geometry, and returns a downloadable GLB. Show the tool-call trace beside the artifact. Include one intentionally invalid request to demonstrate validation and recovery. For photos, ask the VLM for visible scene and style information; obtain names directly from visitor input.

Proposed tool contracts:

- `list_assets`: return asset IDs, styles and license metadata from a curated catalog.
- `inspect_capture`: return visible attributes and confidence from selected frames; planned.
- `personalize_mesh`: accept an asset ID, visitor name and bounded style parameters; wrap the existing script.
- `validate_mesh`: return export checks and geometry findings; current basic checks need extension.
- `render_preview`: produce an image for inspection.
- `package_souvenir`: return artifact paths and provenance.

Use structured arguments, isolated output directories, bounded retries and an allowlist of supported assets. Do not expose arbitrary shell execution as the public application's mesh tool.

## Evaluation

Measure task success, exact name rendering, correct asset selection, repair/retry success, end-to-end latency, GPU memory, and trace completeness. Keep model benchmarks distinct from end-to-end artifact timings. Do not claim printability based on GLB export success.

## Competition alignment

The user identified the NVIDIA DGX Spark hackathon and a requirement for an open-source GitHub repository. The exact event rulebook, submission deadline and judging weights have not been verified. Do not infer those from similarly named events or other teams' repositories.
