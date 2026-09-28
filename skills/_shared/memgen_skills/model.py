"""Offline Qwen adapter. No credentials, network endpoints, or silent mocks."""
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import time
from pathlib import Path

from .common import sha256, validate, write_json


def preflight(model_path=None, media_only=False):
    report = {"python": platform.python_version(), "platform": platform.platform(), "checks": {}}
    for executable in ("ffmpeg", "ffprobe"):
        report["checks"][executable] = shutil.which(executable)
    for module, distribution in (("numpy", "numpy"), ("PIL", "Pillow"), ("jsonschema", "jsonschema")):
        report["checks"][module] = importlib.metadata.version(distribution) if importlib.util.find_spec(module) else None
    if not media_only:
        for module in ("torch", "transformers", "accelerate"):
            report["checks"][module] = importlib.metadata.version(module) if importlib.util.find_spec(module) else None
        if report["checks"].get("torch"):
            import torch
            report["checks"]["cuda"] = torch.cuda.is_available()
            report["device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        else:
            report["checks"]["cuda"] = False
        checkpoint = Path(model_path).expanduser() if model_path else None
        report["checks"]["model_config"] = bool(checkpoint and (checkpoint / "config.json").is_file())
        report["checks"]["model_weights"] = bool(checkpoint and list(checkpoint.glob("*.safetensors")))
        report["checks"]["processor"] = bool(checkpoint and (checkpoint / "preprocessor_config.json").is_file())
        report["checks"]["tokenizer"] = bool(checkpoint and (checkpoint / "tokenizer_config.json").is_file())
    report["ok"] = all(report["checks"].values())
    return report


class LocalQwen:
    def __init__(self, checkpoint):
        self.checkpoint = Path(checkpoint).expanduser().resolve()
        self.model = None
        self.processor = None
        self.load_seconds = 0
        self.calls = 0
        self.inference_seconds = 0
        self.generated_tokens = 0

    def load(self):
        if self.model is not None:
            return
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        if not torch.cuda.is_available():
            raise RuntimeError("Local Qwen requires the configured CUDA host; no cloud fallback is used.")
        start = time.monotonic()
        print("Loading local Qwen:", self.checkpoint, flush=True)
        self.processor = AutoProcessor.from_pretrained(self.checkpoint, local_files_only=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.checkpoint, dtype=torch.bfloat16, device_map="cuda",
            attn_implementation="sdpa", local_files_only=True)
        self.load_seconds = time.monotonic() - start
        print(f"Qwen ready in {self.load_seconds:.1f}s", flush=True)

    def metadata(self):
        result = {"provider": "local_qwen", "checkpoint": str(self.checkpoint),
                  "config_sha256": sha256(self.checkpoint / "config.json"),
                  "offline": True, "load_seconds": self.load_seconds,
                  "calls": self.calls, "inference_seconds": self.inference_seconds,
                  "generated_tokens": self.generated_tokens,
                  "counter_scope": "Cumulative within this model process; selection metrics also record per-run deltas.",
                  "decoding": {"do_sample": False},
                  "image_max_pixels": 262144}
        if self.model is not None:
            import torch
            result["torch"] = torch.__version__
            result["transformers"] = importlib.metadata.version("transformers")
            result["peak_torch_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated()
            result["memory_note"] = "PyTorch CUDA allocations only; not total DGX unified-memory use."
        return result

    def generate(self, prompt, images, max_tokens):
        self.load()
        import torch
        content = [{"type": "text", "text": prompt}]
        for label, path in images:
            content += [{"type": "text", "text": label}, {"type": "image", "url": str(path)}]
        messages = [{"role": "user", "content": content}]
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True,
            return_tensors="pt", enable_thinking=False,
            images_kwargs={"size": {"longest_edge": 262144, "shortest_edge": 4096}}).to("cuda")
        start = time.monotonic()
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
        tokens = output[:, inputs["input_ids"].shape[1]:]
        text = self.processor.batch_decode(tokens, skip_special_tokens=True)[0]
        self.calls += 1
        self.inference_seconds += time.monotonic() - start
        self.generated_tokens += tokens.shape[1]
        return text


def json_reply(model, prompt, contract, images, log_dir, check=None, max_tokens=2500):
    """One initial attempt plus one correction; preserve every request/response."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    base = prompt + "\nReturn ONLY JSON matching this schema:\n" + json.dumps(contract, separators=(",", ":"))
    request = base
    errors = []
    for attempt in range(2):
        prefix = log_dir / f"attempt-{attempt + 1}"
        prefix.with_suffix(".prompt.txt").write_text(request, encoding="utf-8")
        start = time.monotonic()
        raw = model.generate(request, images, max_tokens if attempt == 0 else min(8000, max_tokens * 2))
        prefix.with_suffix(".response.txt").write_text(raw, encoding="utf-8")
        try:
            # Accept one complete JSON fence, never an object guessed from prose.
            fenced = re.fullmatch(r"\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*", raw)
            result = json.loads(fenced.group(1) if fenced else raw)
            # Give the correction every schema error with its exact field path.
            # Never coerce IDs, invent missing observations, or discard invalid rows.
            import jsonschema
            problems = list(jsonschema.Draft202012Validator(contract).iter_errors(result))
            if problems:
                details = []
                for problem in problems[:12]:
                    location = "$" + "".join(f"[{v}]" if isinstance(v, int) else f".{v}" for v in problem.absolute_path)
                    details.append(f"{location}: {problem.message}")
                raise ValueError("\n".join(details))
            result = validate(result, contract)
            if check:
                check(result)
        except (ValueError, TypeError, KeyError) as error:
            errors.append(str(error)[:2000])
        except Exception as error:
            import jsonschema
            if not isinstance(error, jsonschema.ValidationError):
                raise
            errors.append(error.message[:2000])
        else:
            write_json(log_dir / "result.json", result)
            write_json(log_dir / "validation.json", {"valid": True, "attempts": attempt + 1, "prior_errors": errors})
            return result
        write_json(prefix.with_suffix(".error.json"), {"error": errors[-1], "seconds": time.monotonic() - start})
        request = base + "\nYour previous response was invalid:\n" + raw + "\nCorrect this error and return the complete JSON:\n" + errors[-1]
    raise ValueError(f"Model output invalid after one correction. Diagnostics: {log_dir}: {errors[-1]}")
