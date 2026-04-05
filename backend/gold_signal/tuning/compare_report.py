"""
Before / after tuning comparison: metrics on **concatenated OOS** windows only
(same WF steps as the tuning CSV), so production vs tuned are comparable.

**Before** = production ``discrete_from_z`` / ``build_signal_table``.
**After** = per-step τ from CSV; A/B/F also use tuned horizon weights from ``per_category_per_step.csv``.

Consensus **after** is not defined (no joint combiner in the research tuner) — shown as \"—\".
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from gold_signal.backtest.walk_forward import full_sample_return_stats
from gold_signal.config import Settings, settings
from gold_signal.etl.panel import load_raw_panel
from gold_signal.signals.categories import build_signal_table, compute_category_raw_scores
from gold_signal.signals.subsignal_meta import SUBSIGNAL_META
from gold_signal.signals.tuned_overlays import leg_direction_with_csv_taus
from gold_signal.signals.transforms import discrete_deadband, discrete_from_z
from gold_signal.tuning.engine import _strat_returns
from gold_signal.tuning.horizon import raw_a_with_momentum_weights, raw_b_weighted, raw_f_weighted
from gold_signal.tuning.wf_steps import WfStepBounds, iter_wf_step_bounds


def _latest_tuning_dir(root: Path) -> Path | None:
    base = root / "data" / "tuning_runs"
    if not base.is_dir():
        return None
    subs = [p for p in base.iterdir() if p.is_dir()]
    if not subs:
        return None
    return max(subs, key=lambda p: p.stat().st_mtime)


def _fmt_stat(v: float | None) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    return f"{v:.2f}"


def _pack_stats(sr: pd.Series) -> dict[str, str]:
    fs = full_sample_return_stats(sr)
    return {
        "cagr": _fmt_stat(fs.get("total_return_pct")),
        "vol": _fmt_stat(fs.get("volatility_annualized")),
        "sharpe": _fmt_stat(fs.get("annualized_sharpe")),
        "maxdd": _fmt_stat(fs.get("max_drawdown_pct")),
        "days": str(int(fs.get("trading_days") or 0)),
    }


def _oos_concat_slices(daily_ret: pd.Series, bounds: list[WfStepBounds]) -> pd.Series:
    parts = [daily_ret.iloc[b.oos_start : b.oos_end] for b in bounds]
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, ignore_index=True)


def _leg_tau_lookup(leg_df: pd.DataFrame) -> dict[tuple[int, str], float]:
    out: dict[tuple[int, str], float] = {}
    for _, row in leg_df.iterrows():
        sid = str(row["leg_id"])
        si = int(row["step_idx"])
        t = row["tau_star"]
        out[(si, sid)] = float(t) if pd.notna(t) else 0.0
    return out


def _oos_concat_subleg_tuned(
    cat: pd.DataFrame,
    r: pd.Series,
    leg_id: str,
    bounds: list[WfStepBounds],
    step_indices: list[int],
    tau_lu: dict[tuple[int, str], float],
) -> pd.Series:
    z = cat[f"subz_{leg_id}"]
    chunks = []
    if len(bounds) != len(step_indices):
        raise ValueError("bounds and step_indices length mismatch")
    for b, si in zip(bounds, step_indices):
        tau = tau_lu.get((si, leg_id), 0.0)
        d = discrete_deadband(z, tau)
        st = _strat_returns(d, r)
        chunks.append(st.iloc[b.oos_start : b.oos_end])
    return pd.concat(chunks, ignore_index=True) if chunks else pd.Series(dtype=float)


def _cat_row(cat_df: pd.DataFrame, step_idx: int, letter: str) -> pd.Series | None:
    m = cat_df[(cat_df["step_idx"].astype(int) == step_idx) & (cat_df["category"].astype(str) == letter)]
    if m.empty:
        return None
    return m.iloc[0]


def _oos_concat_category_tuned(
    cat: pd.DataFrame,
    r: pd.Series,
    sig: pd.DataFrame,
    cat_df: pd.DataFrame,
    bounds: list[WfStepBounds],
    step_indices: list[int],
    letter: str,
) -> pd.Series:
    col = f"strat_return_{letter}"
    chunks = []
    if len(bounds) != len(step_indices):
        raise ValueError("bounds and step_indices length mismatch")
    for b, si in zip(bounds, step_indices):
        row = _cat_row(cat_df, si, letter)
        if row is None:
            if col in sig.columns:
                chunks.append(sig[col].iloc[b.oos_start : b.oos_end])
            continue
        tau = float(row["tau_star"]) if pd.notna(row["tau_star"]) else 0.0
        if letter == "A":
            w5 = float(row["w5"]) if pd.notna(row["w5"]) else 1.0 / 3.0
            w20 = float(row["w20"]) if pd.notna(row["w20"]) else 1.0 / 3.0
            w60 = float(row["w60"]) if pd.notna(row["w60"]) else 1.0 / 3.0
            raw = raw_a_with_momentum_weights(cat, w5, w20, w60)
        elif letter == "B":
            w1 = float(row["w1"]) if pd.notna(row["w1"]) else 0.25
            w2 = float(row["w2"]) if pd.notna(row["w2"]) else 0.25
            w3 = float(row["w3"]) if pd.notna(row["w3"]) else 0.25
            w4 = float(row["w4"]) if pd.notna(row["w4"]) else 0.25
            raw = raw_b_weighted(cat, w1, w2, w3, w4)
        elif letter == "F":
            wc = float(row["w_cot"]) if pd.notna(row["w_cot"]) else 0.5
            we = float(row["w_etf"]) if pd.notna(row["w_etf"]) else 0.5
            raw = raw_f_weighted(cat, wc, we)
        else:
            raw = cat[f"raw_{letter}"]
        d = discrete_deadband(raw, tau)
        st = _strat_returns(d, r)
        chunks.append(st.iloc[b.oos_start : b.oos_end])
    return pd.concat(chunks, ignore_index=True) if chunks else pd.Series(dtype=float)


@dataclass(frozen=True)
class BeforeAfterCompare:
    """Loaded once; format to markdown or TSV without re-running the panel."""

    run_dir: Path
    step_indices: list[int]
    rows: list[tuple[str, str, dict[str, str], dict[str, str]]]


def load_before_after_compare(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
) -> BeforeAfterCompare:
    cfg = cfg or settings
    root = cfg.project_root
    run_dir = tuning_run_dir or _latest_tuning_dir(root)
    if run_dir is None or not (run_dir / "per_leg_per_step.csv").is_file():
        raise FileNotFoundError(
            f"No tuning run found under {root / 'data' / 'tuning_runs'}. Run scripts/wf_tune_signals.py first."
        )

    leg_df = pd.read_csv(run_dir / "per_leg_per_step.csv")
    cat_df = pd.read_csv(run_dir / "per_category_per_step.csv")

    step_indices = sorted(leg_df["step_idx"].astype(int).unique().tolist())
    if not step_indices:
        raise ValueError("Empty per_leg_per_step.csv")

    data_dir = cfg.resolved_data_dir()
    panel, _ = load_raw_panel(data_dir, cfg)
    cat = compute_category_raw_scores(panel, cfg)
    sig = build_signal_table(panel, cfg)
    r = panel["xauusd"].pct_change(fill_method=None).reindex(cat.index).fillna(0.0)

    all_bounds = iter_wf_step_bounds(len(cat), cfg)
    bounds = [all_bounds[i] for i in step_indices if i < len(all_bounds)]
    if len(bounds) != len(step_indices):
        raise ValueError(
            f"WF step_idx in CSV ({step_indices}) exceeds available bounds ({len(all_bounds)}). "
            "Re-run tuner with same GOLD_WF_* settings."
        )

    thr = float(cfg.threshold)
    tau_lu = _leg_tau_lookup(leg_df)

    table_rows: list[tuple[str, str, dict[str, str], dict[str, str]]] = []

    for leg_id in sorted(leg_df["leg_id"].unique()):
        zc = f"subz_{leg_id}"
        if zc not in cat.columns:
            continue
        d_prod = discrete_from_z(cat[zc], thr)
        st_b = _strat_returns(d_prod, r)
        ser_b = _oos_concat_slices(st_b, bounds)
        st_a = _oos_concat_subleg_tuned(cat, r, leg_id, bounds, step_indices, tau_lu)
        label = SUBSIGNAL_META.get(leg_id, {}).get("label", leg_id)
        table_rows.append((f"Leg: {leg_id}", label, _pack_stats(ser_b), _pack_stats(st_a)))

    for letter in sorted(cat_df["category"].astype(str).unique()):
        col = f"strat_return_{letter}"
        if col not in sig.columns:
            continue
        ser_b = _oos_concat_slices(sig[col], bounds)
        ser_a = _oos_concat_category_tuned(cat, r, sig, cat_df, bounds, step_indices, letter)
        table_rows.append(
            (f"Category {letter} (solo)", f"Composite {letter}", _pack_stats(ser_b), _pack_stats(ser_a))
        )

    ser_cons_b = _oos_concat_slices(sig["strat_return"], bounds)
    empty = pd.Series(dtype=float)
    table_rows.append(
        (
            "Consensus (L/S)",
            "Majority + tie-break (main strategy)",
            _pack_stats(ser_cons_b),
            _pack_stats(empty),
        )
    )

    return BeforeAfterCompare(run_dir=run_dir, step_indices=step_indices, rows=table_rows)


def _tsv_cell(s: str) -> str:
    return s.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _tsv_metric(s: str) -> str:
    """Empty cell for em dash so Excel sees a blank, not text."""
    return "" if s == "—" else s


def before_after_to_tsv(c: BeforeAfterCompare) -> str:
    """Tab-separated table: paste into Excel or open directly."""
    buf = StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        [
            "ID",
            "Strategy",
            "Days",
            "Before CAGR %",
            "Before Vol %",
            "Before Sharpe",
            "Before Max DD %",
            "After CAGR %",
            "After Vol %",
            "After Sharpe",
            "After Max DD %",
        ]
    )
    for rid, lbl, pb, pa in c.rows:
        w.writerow(
            [
                _tsv_cell(rid),
                _tsv_cell(lbl),
                pb["days"],
                _tsv_metric(pb["cagr"]),
                _tsv_metric(pb["vol"]),
                _tsv_metric(pb["sharpe"]),
                _tsv_metric(pb["maxdd"]),
                _tsv_metric(pa["cagr"]),
                _tsv_metric(pa["vol"]),
                _tsv_metric(pa["sharpe"]),
                _tsv_metric(pa["maxdd"]),
            ]
        )
    return buf.getvalue()


def before_after_to_markdown(c: BeforeAfterCompare) -> str:
    run_dir = c.run_dir
    step_indices = c.step_indices
    table_rows = c.rows

    lines = [
        "## Before / after metrics (concatenated OOS windows only)",
        "",
        "All return / vol / Sharpe / max drawdown are computed on **only** the out-of-sample slices "
        f"from WF steps **{step_indices}** (`{run_dir.name}`), stitched end-to-end. "
        "CAGR uses trading-day count of that stitched series.",
        "",
        "| ID | Strategy | Days | **Before** CAGR % | Vol % | Sharpe | Max DD % | **After** CAGR % | Vol % | Sharpe | Max DD % |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for rid, lbl, pb, pa in table_rows:
        lines.append(
            f"| {rid} | {lbl} | {pb['days']} | {pb['cagr']} | {pb['vol']} | {pb['sharpe']} | {pb['maxdd']} | "
            f"{pa['cagr']} | {pa['vol']} | {pa['sharpe']} | {pa['maxdd']} |"
        )

    lines.extend(
        [
            "",
            "### Notes",
            "",
            "- **Before** = production: `discrete_from_z` on legs; category & consensus from `build_signal_table`.",
            "- **After** = tuned τ per step from `per_leg_per_step.csv`; categories use weights + τ from `per_category_per_step.csv`.",
            "- **Consensus / main strategy** has no **After** column (research tuner does not re-fit the majority vote).",
            "",
            f"Excel: use `before_after_metrics.tsv` in this folder (tab-separated), or paste from that file.",
        ]
    )

    return "\n".join(lines)


def build_before_after_markdown(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
) -> str:
    return before_after_to_markdown(load_before_after_compare(tuning_run_dir, cfg))


def build_before_after_tsv(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
) -> str:
    return before_after_to_tsv(load_before_after_compare(tuning_run_dir, cfg))


def write_compare_reports(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
    *,
    data: BeforeAfterCompare | None = None,
) -> tuple[Path, Path]:
    """Writes `before_after_metrics.md` and `before_after_metrics.tsv` next to the tuning run."""
    c = data if data is not None else load_before_after_compare(tuning_run_dir, cfg)
    md_path = c.run_dir / "before_after_metrics.md"
    tsv_path = c.run_dir / "before_after_metrics.tsv"
    md_path.write_text(before_after_to_markdown(c), encoding="utf-8")
    tsv_path.write_text(before_after_to_tsv(c), encoding="utf-8")
    return md_path, tsv_path


def write_compare_markdown(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
) -> Path:
    md_path, _ = write_compare_reports(tuning_run_dir, cfg)
    return md_path


def _load_full_sample_tuning_context(
    tuning_run_dir: Path | None,
    cfg: Settings,
) -> tuple[Path, pd.DataFrame, dict[tuple[int, str], float], pd.DataFrame, pd.Series, list[WfStepBounds], float]:
    root = cfg.project_root
    run_dir = tuning_run_dir or _latest_tuning_dir(root)
    if run_dir is None or not (run_dir / "per_leg_per_step.csv").is_file():
        raise FileNotFoundError(
            f"No tuning run found under {root / 'data' / 'tuning_runs'}. Run scripts/wf_tune_signals.py first."
        )
    leg_df = pd.read_csv(run_dir / "per_leg_per_step.csv")
    tau_lu = _leg_tau_lookup(leg_df)
    data_dir = cfg.resolved_data_dir()
    panel, _ = load_raw_panel(data_dir, cfg)
    cat = compute_category_raw_scores(panel, cfg)
    r = panel["xauusd"].pct_change(fill_method=None).reindex(cat.index).fillna(0.0)
    bounds = iter_wf_step_bounds(len(cat), cfg)
    thr = float(cfg.threshold)
    return run_dir, leg_df, tau_lu, cat, r, bounds, thr


def _full_sample_leg_row_dict(
    leg_id: str,
    run_dir: Path,
    leg_df: pd.DataFrame,
    tau_lu: dict[tuple[int, str], float],
    cat: pd.DataFrame,
    r: pd.Series,
    bounds: list[WfStepBounds],
    thr: float,
) -> dict:
    z = cat[f"subz_{leg_id}"]
    d_before = discrete_from_z(z, thr)
    st_before = _strat_returns(d_before, r)
    d_after = leg_direction_with_csv_taus(z, bounds, leg_id, tau_lu, thr)
    st_after = _strat_returns(d_after, r)

    idx = z.index
    csv_steps = sorted(
        leg_df.loc[leg_df["leg_id"].astype(str) == leg_id, "step_idx"].astype(int).unique().tolist()
    )
    overlay = np.zeros(len(z), dtype=bool)
    for b in bounds:
        if (b.step_idx, leg_id) in tau_lu:
            overlay[b.is_start : b.oos_end] = True
    n_overlay_days = int(overlay.sum())
    n = int(len(z))

    return {
        "leg_id": leg_id,
        "label": SUBSIGNAL_META.get(leg_id, {}).get("label", leg_id),
        "category": SUBSIGNAL_META.get(leg_id, {}).get("category", ""),
        "tuning_run": run_dir.name,
        "tuning_run_dir": str(run_dir.resolve()),
        "first_date": str(idx[0].date()) if n else None,
        "last_date": str(idx[-1].date()) if n else None,
        "n_trading_days": n,
        "n_wf_steps": len(bounds),
        "n_tau_overlays": sum(1 for b in bounds if (b.step_idx, leg_id) in tau_lu),
        "csv_step_indices": csv_steps,
        "n_csv_steps": len(csv_steps),
        "n_days_under_tau_overlay": n_overlay_days,
        "pct_days_under_tau_overlay": round(100.0 * n_overlay_days / n, 4) if n else 0.0,
        "before": full_sample_return_stats(st_before),
        "after": full_sample_return_stats(st_after),
        "buy_hold": full_sample_return_stats(r),
    }


def full_sample_leg_before_after_tuned(
    leg_id: str,
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
) -> dict:
    """
    Full backtest: production leg vs same leg with **per–WF-step τ** from ``per_leg_per_step.csv``
    overlaid on each matching block ``[is_start, oos_end)``.

    Requires the same ``GOLD_WF_*`` (and panel length) as when the CSV was produced; otherwise
    ``step_idx`` alignment is meaningless.

    Returns ``before`` / ``after`` / ``buy_hold`` dicts from ``full_sample_return_stats`` on
    lagged-direction × XAU daily returns.
    """
    cfg = cfg or settings
    run_dir, leg_df, tau_lu, cat, r, bounds, thr = _load_full_sample_tuning_context(tuning_run_dir, cfg)
    zc = f"subz_{leg_id}"
    if zc not in cat.columns:
        raise KeyError(f"No column {zc} for leg_id={leg_id!r}")
    return _full_sample_leg_row_dict(leg_id, run_dir, leg_df, tau_lu, cat, r, bounds, thr)


def full_sample_all_legs_batch(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
) -> dict:
    """
    One panel load; full-sample before/after/buy-hold for every ``leg_id`` present in
    ``per_leg_per_step.csv`` that has ``subz_<leg_id>`` in the category table.

    Returns ``{"shared": {...}, "legs": [ per-leg dict, ... ]}``.
    """
    cfg = cfg or settings
    run_dir, leg_df, tau_lu, cat, r, bounds, thr = _load_full_sample_tuning_context(tuning_run_dir, cfg)
    idx = cat.index
    n = len(idx)
    shared = {
        "first_date": str(idx[0].date()) if n else None,
        "last_date": str(idx[-1].date()) if n else None,
        "n_trading_days": n,
        "n_wf_steps": len(bounds),
        "tuning_run": run_dir.name,
        "tuning_run_dir": str(run_dir.resolve()),
        "n_legs_in_csv": int(leg_df["leg_id"].nunique()),
        "n_unique_csv_steps": int(leg_df["step_idx"].nunique()),
        "buy_hold": full_sample_return_stats(r),
    }
    legs: list[dict] = []
    for leg_id in sorted(leg_df["leg_id"].astype(str).unique()):
        zc = f"subz_{leg_id}"
        if zc not in cat.columns:
            continue
        legs.append(_full_sample_leg_row_dict(leg_id, run_dir, leg_df, tau_lu, cat, r, bounds, thr))
    return {"shared": shared, "legs": legs}


def full_sample_leg_report_markdown(out: dict) -> str:
    """Human-readable report: full calendar + stats (from ``full_sample_leg_before_after_tuned``)."""
    lines = [
        "## Full-sample leg backtest (entire merged panel)",
        "",
        f"- **Leg:** `{out['leg_id']}` — {out['label']}",
        f"- **Calendar:** **{out['first_date']}** → **{out['last_date']}** ({out['n_trading_days']:,} trading days)",
        f"- **Tuning run:** `{out['tuning_run']}`",
        f"- **WF blocks** in this panel: {out['n_wf_steps']} | **CSV step_idx** for this leg: {out['n_csv_steps']} {out['csv_step_indices']}",
        f"- **Days using τ overlay** on `[is_start, oos_end)` for those CSV steps: **{out['n_days_under_tau_overlay']:,}** "
        f"({out['pct_days_under_tau_overlay']:.2f}% of history). All other days = production `discrete_from_z`.",
        "",
        "### Metrics (lagged direction × XAU daily return, full series)",
        "",
        "| | Sharpe | CAGR % | Vol % | Max DD % | Trading days |",
        "|---|--:|--:|--:|--:|--:|",
    ]

    def cells(d: dict) -> tuple[str, str, str, str, str]:
        def f(v: float | None, nd: int) -> str:
            if v is None or (isinstance(v, float) and v != v):
                return "—"
            return f"{v:.{nd}f}"

        return (
            f(d.get("annualized_sharpe"), 4),
            f(d.get("total_return_pct"), 2),
            f(d.get("volatility_annualized"), 2),
            f(d.get("max_drawdown_pct"), 2),
            str(int(d.get("trading_days") or 0)),
        )

    for name, key in [
        ("Before (production `discrete_from_z`)", "before"),
        ("After (CSV τ on WF blocks; else production)", "after"),
        ("Buy & hold XAU (same calendar)", "buy_hold"),
    ]:
        sh, cg, vo, dd, td = cells(out[key])
        lines.append(f"| {name} | {sh} | {cg} | {vo} | {dd} | {td} |")

    lines.extend(
        [
            "",
            "### Note",
            "",
            "If **CSV step count** ≪ **WF blocks**, most of history stays production; re-run `scripts/wf_tune_signals.py` "
            "with all steps (unset `GOLD_WF_MAX_STEPS`) so “after” uses τ across the full timeline.",
        ]
    )
    return "\n".join(lines)


def full_sample_leg_report_tsv(out: dict) -> str:
    buf = StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        ["leg_id", "label", "first_date", "last_date", "n_trading_days", "metric_row", "sharpe", "cagr_pct", "vol_pct", "maxdd_pct"]
    )
    meta = [out["leg_id"], out["label"], out["first_date"], out["last_date"], out["n_trading_days"]]

    def nums(d: dict) -> tuple[str, str, str, str]:
        def g(k: str) -> str:
            v = d.get(k)
            if v is None or (isinstance(v, float) and v != v):
                return ""
            if k == "annualized_sharpe":
                return f"{float(v):.6f}"
            return f"{float(v):.4f}"

        return (g("annualized_sharpe"), g("total_return_pct"), g("volatility_annualized"), g("max_drawdown_pct"))

    for label, key in [("before_production", "before"), ("after_csv_tau", "after"), ("buy_hold_xau", "buy_hold")]:
        sh, cg, vo, dd = nums(out[key])
        w.writerow([*meta, label, sh, cg, vo, dd])
    return buf.getvalue()


def write_full_sample_leg_reports(
    leg_id: str,
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
    *,
    data: dict | None = None,
) -> tuple[Path, Path]:
    """Writes `full_sample_<leg_id>.md` and `.tsv` under the tuning run directory."""
    out = data if data is not None else full_sample_leg_before_after_tuned(leg_id, tuning_run_dir, cfg)
    run_dir = Path(out["tuning_run_dir"])
    safe = leg_id.replace("/", "_")
    md_p = run_dir / f"full_sample_{safe}.md"
    tsv_p = run_dir / f"full_sample_{safe}.tsv"
    md_p.write_text(full_sample_leg_report_markdown(out), encoding="utf-8")
    tsv_p.write_text(full_sample_leg_report_tsv(out), encoding="utf-8")
    return md_p, tsv_p


def _md_num(v: float | None, nd: int) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    return f"{v:.{nd}f}"


def full_sample_all_legs_report_markdown(batch: dict) -> str:
    s = batch["shared"]
    legs: list[dict] = batch["legs"]
    bh = s["buy_hold"]
    lines = [
        "## Full-sample backtest — all sub-strategies (entire merged panel)",
        "",
        f"- **Calendar:** **{s['first_date']}** → **{s['last_date']}** ({s['n_trading_days']:,} trading days)",
        f"- **Tuning run:** `{s['tuning_run']}`",
        f"- **WF blocks** in panel: {s['n_wf_steps']} | **Distinct step_idx in CSV:** {s['n_unique_csv_steps']} | **Legs in table:** {len(legs)}",
        "",
        "### Buy & hold XAU (same calendar, all rows)",
        "",
        f"| Sharpe | CAGR % | Vol % | Max DD % |",
        f"|--:|--:|--:|--:|",
        f"| {_md_num(bh.get('annualized_sharpe'), 4)} | {_md_num(bh.get('total_return_pct'), 2)} | "
        f"{_md_num(bh.get('volatility_annualized'), 2)} | {_md_num(bh.get('max_drawdown_pct'), 2)} |",
        "",
        "### Each leg: production vs CSV τ overlay (full history)",
        "",
        "After = `discrete_deadband` with τ from CSV on each WF block `[is_start, oos_end)` where that step exists; "
        "all other days = production `discrete_from_z`. **%τ** = share of trading days inside those blocks for this leg.",
        "",
        "| Leg | Label | Cat | CSV steps | %τ days | Bef Sharpe | Bef CAGR | Bef Vol | Bef MaxDD | Aft Sharpe | Aft CAGR | Aft Vol | Aft MaxDD |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for row in legs:
        b, a = row["before"], row["after"]
        lines.append(
            f"| `{row['leg_id']}` | {row['label']} | {row.get('category', '')} | {row['n_csv_steps']} | "
            f"{row['pct_days_under_tau_overlay']:.2f} | "
            f"{_md_num(b.get('annualized_sharpe'), 4)} | {_md_num(b.get('total_return_pct'), 2)} | "
            f"{_md_num(b.get('volatility_annualized'), 2)} | {_md_num(b.get('max_drawdown_pct'), 2)} | "
            f"{_md_num(a.get('annualized_sharpe'), 4)} | {_md_num(a.get('total_return_pct'), 2)} | "
            f"{_md_num(a.get('volatility_annualized'), 2)} | {_md_num(a.get('max_drawdown_pct'), 2)} |"
        )
    lines.extend(
        [
            "",
            "### Note",
            "",
            "If CSV has few `step_idx` vs WF blocks, **%τ days** is small and “after” ≈ “before”. "
            "Re-run `scripts/wf_tune_signals.py` without `GOLD_WF_MAX_STEPS` for τ across the full timeline.",
        ]
    )
    return "\n".join(lines)


def full_sample_all_legs_report_tsv(batch: dict) -> str:
    s = batch["shared"]
    buf = StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        [
            "panel_first_date",
            "panel_last_date",
            "n_trading_days",
            "tuning_run",
            "leg_id",
            "label",
            "category",
            "n_csv_steps",
            "pct_days_tau_overlay",
            "before_sharpe",
            "before_cagr_pct",
            "before_vol_pct",
            "before_maxdd_pct",
            "after_sharpe",
            "after_cagr_pct",
            "after_vol_pct",
            "after_maxdd_pct",
            "bh_sharpe",
            "bh_cagr_pct",
            "bh_vol_pct",
            "bh_maxdd_pct",
        ]
    )

    def g(d: dict, k: str) -> str:
        v = d.get(k)
        if v is None or (isinstance(v, float) and v != v):
            return ""
        return f"{float(v):.6f}" if k == "annualized_sharpe" else f"{float(v):.4f}"

    bh = s["buy_hold"]
    bh_sh, bh_cg, bh_vo, bh_dd = (
        g(bh, "annualized_sharpe"),
        g(bh, "total_return_pct"),
        g(bh, "volatility_annualized"),
        g(bh, "max_drawdown_pct"),
    )
    meta0 = [s["first_date"], s["last_date"], s["n_trading_days"], s["tuning_run"]]

    for row in batch["legs"]:
        b, a = row["before"], row["after"]
        w.writerow(
            [
                *meta0,
                row["leg_id"],
                row["label"],
                row.get("category", ""),
                row["n_csv_steps"],
                f"{row['pct_days_under_tau_overlay']:.4f}",
                g(b, "annualized_sharpe"),
                g(b, "total_return_pct"),
                g(b, "volatility_annualized"),
                g(b, "max_drawdown_pct"),
                g(a, "annualized_sharpe"),
                g(a, "total_return_pct"),
                g(a, "volatility_annualized"),
                g(a, "max_drawdown_pct"),
                bh_sh,
                bh_cg,
                bh_vo,
                bh_dd,
            ]
        )
    return buf.getvalue()


def write_full_sample_all_legs_reports(
    tuning_run_dir: Path | None = None,
    cfg: Settings | None = None,
    *,
    data: dict | None = None,
) -> tuple[Path, Path]:
    """Writes `full_sample_all_legs.md` and `full_sample_all_legs.tsv` under the tuning run directory."""
    batch = data if data is not None else full_sample_all_legs_batch(tuning_run_dir, cfg)
    run_dir = Path(batch["shared"]["tuning_run_dir"])
    md_p = run_dir / "full_sample_all_legs.md"
    tsv_p = run_dir / "full_sample_all_legs.tsv"
    md_p.write_text(full_sample_all_legs_report_markdown(batch), encoding="utf-8")
    tsv_p.write_text(full_sample_all_legs_report_tsv(batch), encoding="utf-8")
    return md_p, tsv_p
