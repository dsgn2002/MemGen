#!/usr/bin/env python3
"""Bundle preflight, artifact validation, and matched-budget evaluation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_shared"))
from memgen_skills.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
