"""Strict artifacts, subprocesses, and run isolation."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

import jsonschema

BUNDLE = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema(name):
    skill = "trip-intent-understanding" if name.startswith("intent") else "video-evidence-selection"
    return read_json(BUNDLE / skill / "references" / (name + ".schema.json"))


def validate(value, contract):
    jsonschema.Draft202012Validator(contract).validate(value)
    return value


def fresh_run(path):
    path = Path(path).expanduser().resolve()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"Output must be a new or empty directory: {path}. Use a fresh run to retain diagnostics.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_path(run, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Asset path must be relative within the run: {relative}")
    result = (Path(run) / path).resolve()
    if not result.is_relative_to(Path(run).resolve()):
        raise ValueError("Asset resolves outside the run")
    return result


def command(argv, timeout=180):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{Path(str(argv[0])).name} failed: {result.stderr[-1800:]}")
    return result.stdout


def finite_positive(value, label):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite")
    return value
