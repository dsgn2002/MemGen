"""Portable CLI entrypoints; importing this module never loads a model."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from .common import fresh_run, read_json, sha256, write_json
from .evidence import recheck_run, run_selection, validate_brief
from .intent import understand, validate_intent
from .model import LocalQwen, preflight


def parser():
    p = argparse.ArgumentParser(description="MemGen local trip-intent and video-evidence skills")
    sub = p.add_subparsers(dest="command", required=True)
    check = sub.add_parser("preflight")
    check.add_argument("--media-only", action="store_true")
    commands = [check]
    intent = sub.add_parser("understand")
    intent.add_argument("--request-file", type=Path, required=True)
    intent.add_argument("--context-file", type=Path)
    intent.add_argument("--out", type=Path, required=True)
    commands.append(intent)
    evidence = sub.add_parser("select")
    evidence.add_argument("--video", type=Path, required=True)
    evidence.add_argument("--intent", type=Path, required=True)
    evidence.add_argument("--out", type=Path, required=True)
    evidence.add_argument("--strategy", choices=["adaptive", "uniform"], default="adaptive")
    evidence.add_argument("--moments", type=int, choices=range(1, 11))
    commands.append(evidence)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--video", type=Path, required=True)
    evaluate.add_argument("--cases", type=Path, required=True)
    evaluate.add_argument("--out", type=Path, required=True)
    evaluate.add_argument("--skip-baseline", action="store_true", help="Smoke test only; does not satisfy baseline acceptance")
    evaluate.add_argument("--reuse-completed", type=Path, help="Explicitly recheck completed runs from this root; missing runs execute normally. Staged timings are labeled.")
    commands.append(evaluate)
    recheck = sub.add_parser("recheck", help="Recheck recorded source observations with local Qwen into a fresh directory")
    recheck.add_argument("--video", type=Path, required=True)
    recheck.add_argument("--prior", type=Path, required=True)
    recheck.add_argument("--out", type=Path, required=True)
    commands.append(recheck)
    for cmd in commands:
        cmd.add_argument("--model-path", type=Path, default=os.environ.get("MEMGEN_QWEN_MODEL"))
    for cmd in (evidence, evaluate):
        cmd.add_argument("--coarse-budget", type=int, default=96)
        cmd.add_argument("--refinement-budget", type=int, default=24)
        cmd.add_argument("--batch-size", type=int, default=6)
    verify = sub.add_parser("validate")
    verify.add_argument("path", type=Path)
    verify.add_argument("--video", type=Path, help="Also verify original video checksum")
    return p


def execute(args):
    if args.command == "validate":
        value = read_json(args.path)
        if "moments" in value:
            validate_brief(value, args.path.resolve().parent)
            if args.video and sha256(args.video) != value["source"]["sha256"]:
                raise ValueError("Original source video checksum mismatch")
        else:
            validate_intent(value)
        print("VALID", args.path)
        return
    report = preflight(args.model_path, media_only=getattr(args, "media_only", False))
    if args.command == "preflight":
        print(json.dumps(report, indent=2))
        if not report["ok"]:
            raise RuntimeError("Preflight failed; configure the documented existing environment/model")
        return
    if not report["ok"]:
        raise RuntimeError("Preflight failed: " + json.dumps(report))
    if args.command == "understand":
        request = args.request_file.read_text(encoding="utf-8")
        context = args.context_file.read_text(encoding="utf-8") if args.context_file else ""
        run = fresh_run(args.out)
        args._run_owned = True
        write_json(run / "preflight.json", report)
        understand(LocalQwen(args.model_path), request, run, context)
        print("Intent ready:", run / "intent.json")
    elif args.command == "recheck":
        run = fresh_run(args.out)
        args._run_owned = True
        write_json(run / "preflight.json", report)
        recheck_run(LocalQwen(args.model_path), args.video.resolve(), args.prior.resolve(), run)
    elif args.command == "select":
        intent = validate_intent(read_json(args.intent))
        run = fresh_run(args.out)
        args._run_owned = True
        write_json(run / "preflight.json", report)
        run_selection(LocalQwen(args.model_path), args.video.resolve(), intent, run,
                      args.coarse_budget, args.refinement_budget, args.batch_size, args.strategy, args.moments)
    else:
        cases = read_json(args.cases)["cases"]
        if not cases or any(not isinstance(c.get("request"), str) or not c["request"].strip() for c in cases):
            raise ValueError("Evaluation cases need nonempty requests")
        identifiers = [c["id"] for c in cases]
        if len(set(identifiers)) != len(identifiers) or any(not s.replace("-", "").isalnum() for s in identifiers):
            raise ValueError("Case IDs must be unique alphanumeric/hyphen names")
        root = fresh_run(args.out)
        args._run_owned = True
        write_json(root / "preflight.json", report)
        model = LocalQwen(args.model_path)
        rows = []
        start = time.monotonic()
        for case in cases:
            run = fresh_run(root / case["id"] / "intent")
            intent = understand(model, case["request"], run, case.get("context", ""))
            # Identical model + prompt + budgets, only candidate sampling strategy differs.
            for strategy in (["adaptive"] if args.skip_baseline else ["adaptive", "uniform"]):
                run = fresh_run(root / case["id"] / strategy)
                prior = args.reuse_completed / case["id"] / strategy if args.reuse_completed else None
                if prior and (prior / "evidence-brief.json").is_file():
                    old = read_json(prior / "evidence-brief.json")
                    if any(old["sampling"][key] != getattr(args, key) for key in ("coarse_budget", "refinement_budget", "batch_size")) or old["sampling"]["strategy"] != strategy:
                        raise ValueError("Reused sampling settings must match requested comparison")
                    brief = recheck_run(model, args.video.resolve(), prior.resolve(), run, intent)
                else:
                    brief = run_selection(model, args.video.resolve(), intent, run,
                                          args.coarse_budget, args.refinement_budget, args.batch_size, strategy)
                rows.append({"case": case["id"], "strategy": strategy, "metrics": brief["metrics"],
                             "hero_timestamps_s": [m["hero_timestamp_s"] for m in brief["moments"]],
                             "brief": str((run / "evidence-brief.json").relative_to(root))})
                write_json(root / "comparison.json", {"status": "in_progress", "rows": rows})
        write_json(root / "comparison.json", {"status": "completed", "rows": rows,
                   "elapsed_seconds": time.monotonic() - start, "model": model.metadata(),
                   "execution_note": "Wall time for this invocation. Rechecked rows explicitly include prior-run plus recheck cost; see row timing notes." if args.reuse_completed else "Fresh execution; cold model load is reported separately.",
                   "method": "Same local model, intent, configured frame budget, decoding, and final selector; adaptive vs uniform candidate sampling. Cold model load reported separately. Human factual review still required.",
                   "generalization": "One source video; broader generalization has not been established."})
        print("Comparison ready:", root / "comparison.json")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        execute(args)
    except (Exception, KeyboardInterrupt) as error:
        if getattr(args, "_run_owned", False) and Path(args.out).is_dir():
            # Do not overwrite any pre-existing run on a fresh_run rejection.
            failure = Path(args.out) / "failure.json"
            if not failure.exists() and "Output must be a new" not in str(error):
                write_json(failure, {"error": str(error), "type": type(error).__name__})
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0
