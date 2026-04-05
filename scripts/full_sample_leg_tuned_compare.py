#!/usr/bin/env python3
"""Full-sample before vs after (CSV τ overlays): one leg or ``--all`` legs; writes reports under the tuning run."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
os.environ.setdefault("GOLD_DATA_DIR", str(ROOT / "data"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("leg_id", nargs="?", default="A_curve", help="Sub-leg id when not using --all (default A_curve)")
    p.add_argument(
        "--all",
        action="store_true",
        help="All legs in per_leg_per_step.csv (writes full_sample_all_legs.md/.tsv)",
    )
    p.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Tuning run directory (default: latest under data/tuning_runs)",
    )
    p.add_argument("--json", action="store_true", help="Print JSON only (no files)")
    p.add_argument("--no-save", action="store_true", help="Do not write .md / .tsv next to tuning run")
    p.add_argument("--no-open", action="store_true", help="Do not open the .md on macOS")
    args = p.parse_args()

    if args.all:
        from gold_signal.tuning.compare_report import (
            full_sample_all_legs_batch,
            full_sample_all_legs_report_markdown,
            write_full_sample_all_legs_reports,
        )

        batch = full_sample_all_legs_batch(args.run_dir)
        if args.json:
            print(json.dumps(batch, indent=2, default=str))
            return
        if args.no_save:
            print(full_sample_all_legs_report_markdown(batch))
            return

        s = batch["shared"]
        legs = batch["legs"]
        print()
        print("=" * 72)
        print("  FULL SAMPLE — ALL SUB-STRATEGIES (entire merged panel)")
        print("=" * 72)
        print(f"  Calendar:   {s['first_date']}  →  {s['last_date']}  |  {s['n_trading_days']:,} days")
        print(f"  Legs:       {len(legs)}  |  WF blocks: {s['n_wf_steps']}  |  CSV steps: {s['n_unique_csv_steps']}")
        print(f"  Tuning run: {s['tuning_run']}")
        print("=" * 72)
        print()

        if s["n_unique_csv_steps"] < s["n_wf_steps"]:
            print(
                "  WARNING: CSV only lists part of the WF timeline — τ overlays cover a small % of history.\n"
                "            Re-run wf_tune_signals without GOLD_WF_MAX_STEPS for full-history τ.\n",
                file=sys.stderr,
            )

        md_p, tsv_p = write_full_sample_all_legs_reports(data=batch)
        print("Saved summary sheet:", file=sys.stderr)
        print(f"  {md_p}", file=sys.stderr)
        print(f"  {tsv_p}", file=sys.stderr)
        if platform.system() == "Darwin" and not args.no_open:
            subprocess.run(["open", str(md_p)], check=False)
        return

    from gold_signal.tuning.compare_report import (
        full_sample_leg_before_after_tuned,
        full_sample_leg_report_markdown,
        write_full_sample_leg_reports,
    )

    out = full_sample_leg_before_after_tuned(args.leg_id, tuning_run_dir=args.run_dir)
    if args.json:
        print(json.dumps(out, indent=2, default=str))
        return

    if args.no_save:
        print(full_sample_leg_report_markdown(out))
        return

    print()
    print("=" * 72)
    print("  FULL SAMPLE BACKTEST — entire merged panel (not one WF window)")
    print("=" * 72)
    print()
    print(f"  Leg:        {out['leg_id']} — {out['label']}")
    print(f"  Calendar:   {out['first_date']}  →  {out['last_date']}")
    print(f"  Days:       {out['n_trading_days']:,} trading days")
    print(f"  WF blocks:  {out['n_wf_steps']}  |  CSV step_idx for this leg: {out['n_csv_steps']} {out['csv_step_indices']}")
    print(
        f"  τ overlay:  {out['n_days_under_tau_overlay']:,} days "
        f"({out['pct_days_under_tau_overlay']:.2f}% of history) use CSV τ on WF blocks; rest = production."
    )
    print(f"  Tuning run: {out['tuning_run']}")
    print()

    if out["n_tau_overlays"] < out["n_wf_steps"]:
        print(
            "  WARNING: CSV only lists part of the WF timeline — most days stay production.\n"
            "            Re-run wf_tune_signals without GOLD_WF_MAX_STEPS for full-history τ.\n",
            file=sys.stderr,
        )

    def fmt(v, spec: str) -> str:
        if v is None or (isinstance(v, float) and v != v):
            return "—"
        return format(v, spec)

    def row(name: str, d: dict) -> None:
        print(
            f"  {name:22}  Sharpe {fmt(d.get('annualized_sharpe'), '>8.4f')}  "
            f"CAGR % {fmt(d.get('total_return_pct'), '>8.2f')}  "
            f"Vol % {fmt(d.get('volatility_annualized'), '>7.2f')}  "
            f"MaxDD % {fmt(d.get('max_drawdown_pct'), '>7.2f')}"
        )

    print("  --- Metrics (same definitions as dashboard full_sample_return_stats) ---")
    row("Before (production)", out["before"])
    row("After (CSV τ blocks)", out["after"])
    row("Buy & hold XAU", out["buy_hold"])
    print()
    print("=" * 72)
    print()

    md_p, tsv_p = write_full_sample_leg_reports(args.leg_id, tuning_run_dir=args.run_dir, data=out)
    print("Saved full-history report:", file=sys.stderr)
    print(f"  {md_p}", file=sys.stderr)
    print(f"  {tsv_p}", file=sys.stderr)
    if platform.system() == "Darwin" and not args.no_open:
        subprocess.run(["open", str(md_p)], check=False)


if __name__ == "__main__":
    main()
