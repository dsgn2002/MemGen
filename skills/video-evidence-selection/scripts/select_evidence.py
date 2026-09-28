#!/usr/bin/env python3
"""Run from any working directory; distribute with skills/_shared."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from memgen_skills.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["select", *sys.argv[1:]]))
