"""``python -m gold_signal.tuning.cli`` entry (same as scripts/wf_tune_signals.py)."""

from __future__ import annotations

from gold_signal.tuning.engine import run_wf_tune


def main() -> None:
    out = run_wf_tune()
    print(f"Wrote tuning run to {out}")


if __name__ == "__main__":
    main()
