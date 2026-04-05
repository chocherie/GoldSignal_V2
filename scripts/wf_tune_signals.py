#!/usr/bin/env python3
"""
Research-only walk-forward tuning (per-leg τ, category horizon weights + τ).
Writes CSV + JSON under data/tuning_runs/<timestamp>/.

Run it in either of these ways (replace the path with **your** clone — do not use
literal ``/path/to/...`` from docs):

  cd "/Users/you/cursor_projects/Gold Dashboard V2"
  python3 scripts/wf_tune_signals.py

Or from any directory, pass the **absolute path** to this file (so Python finds it):

  python3 "/Users/you/cursor_projects/Gold Dashboard V2/scripts/wf_tune_signals.py"

``PYTHONPATH`` is optional; the script adds ``<repo>/backend`` automatically.

Env: GOLD_DATA_DIR, GOLD_TUNE_TAU_N, GOLD_WF_MAX_STEPS, GOLD_INCLUDE_GPR, GOLD_WF_*.
See specs/wf-tuning-research.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
os.environ.setdefault("GOLD_DATA_DIR", str(ROOT / "data"))


def main() -> None:
    from gold_signal.tuning.engine import run_wf_tune

    print(f"Repo root: {ROOT}")
    out = run_wf_tune()
    print(f"Wrote tuning run to {out}")


if __name__ == "__main__":
    main()
