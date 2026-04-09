"""
Apply walk-forward tuning CSVs (per-leg τ; per-category weights + τ) on top of production z-scores.

Used when ``GOLD_USE_LATEST_TUNING=1`` (or explicit ``GOLD_TUNING_RUN_DIR``): each WF block
``[is_start, oos_end)`` gets parameters from the CSV row for that ``step_idx``; all other
bars stay production ``discrete_from_z``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gold_signal.config import Settings, settings
from gold_signal.signals.transforms import discrete_deadband, discrete_from_z
from gold_signal.tuning.horizon import raw_a_with_momentum_weights, raw_b_weighted, raw_f_weighted
from gold_signal.tuning.wf_steps import WfStepBounds, iter_wf_step_bounds


def resolve_tuning_run_dir(cfg: Settings | None = None) -> Path | None:
    cfg = cfg or settings
    env_dir = (cfg.tuning_run_dir or "").strip()
    if env_dir:
        p = Path(env_dir)
        if not p.is_absolute():
            p = cfg.project_root / p
        if p.is_dir() and (p / "per_leg_per_step.csv").is_file():
            return p.resolve()
        return None
    if not cfg.use_latest_tuning:
        return None
    base = cfg.project_root / "data" / "tuning_runs"
    if not base.is_dir():
        return None
    subs = [x for x in base.iterdir() if x.is_dir() and (x / "per_leg_per_step.csv").is_file()]
    if not subs:
        return None
    return max(subs, key=lambda x: x.stat().st_mtime).resolve()


def tuning_run_mtime(run_dir: Path | None) -> float:
    if run_dir is None or not run_dir.is_dir():
        return 0.0
    p = run_dir / "per_leg_per_step.csv"
    return p.stat().st_mtime if p.is_file() else 0.0


def _leg_tau_lookup(leg_df: pd.DataFrame) -> dict[tuple[int, str], float]:
    out: dict[tuple[int, str], float] = {}
    for _, row in leg_df.iterrows():
        sid = str(row["leg_id"])
        si = int(row["step_idx"])
        t = row["tau_star"]
        out[(si, sid)] = float(t) if pd.notna(t) else 0.0
    return out


def leg_direction_with_csv_taus(
    z: pd.Series,
    bounds: list[WfStepBounds],
    leg_id: str,
    tau_lu: dict[tuple[int, str], float],
    threshold: float,
) -> pd.Series:
    d = discrete_from_z(z, threshold).astype(float).copy()
    for b in sorted(bounds, key=lambda x: x.step_idx):
        key = (b.step_idx, leg_id)
        if key not in tau_lu:
            continue
        tau = tau_lu[key]
        sl = slice(b.is_start, b.oos_end)
        subz = z.iloc[sl]
        d.iloc[sl] = discrete_deadband(subz, tau).to_numpy(dtype=float, copy=False)
    return d


def _cat_row(cat_df: pd.DataFrame, step_idx: int, letter: str) -> pd.Series | None:
    m = cat_df[(cat_df["step_idx"].astype(int) == step_idx) & (cat_df["category"].astype(str) == letter)]
    if m.empty:
        return None
    return m.iloc[0]


def _apply_category_block(
    cat: pd.DataFrame,
    bounds: list[WfStepBounds],
    cat_df: pd.DataFrame,
    letter: str,
    thr: float,
) -> pd.Series:
    raw = cat[f"raw_{letter}"]
    d = discrete_from_z(raw, thr).astype(float).copy()
    for b in sorted(bounds, key=lambda x: x.step_idx):
        row = _cat_row(cat_df, b.step_idx, letter)
        if row is None:
            continue
        tau = float(row["tau_star"]) if pd.notna(row["tau_star"]) else 0.0
        sl = slice(b.is_start, b.oos_end)
        if letter == "A":
            w5 = float(row["w5"]) if pd.notna(row["w5"]) else 1.0 / 3.0
            w20 = float(row["w20"]) if pd.notna(row["w20"]) else 1.0 / 3.0
            w60 = float(row["w60"]) if pd.notna(row["w60"]) else 1.0 / 3.0
            raw_w = raw_a_with_momentum_weights(cat, w5, w20, w60)
            blk = raw_w.iloc[sl]
        elif letter == "B":
            # v3: B has 3 legs (shadow removed): nom, real, 2s10s
            w1 = float(row["w1"]) if pd.notna(row["w1"]) else 1.0 / 3.0
            w2 = float(row["w2"]) if pd.notna(row["w2"]) else 1.0 / 3.0
            # w3 was shadow in v2; skip it if present, use w4 (or w3) as 2s10s weight
            if "w4" in row.index and pd.notna(row["w4"]):
                w3_2s10s = float(row["w4"])
            elif "w3" in row.index and pd.notna(row["w3"]):
                w3_2s10s = float(row["w3"])
            else:
                w3_2s10s = 1.0 / 3.0
            raw_w = raw_b_weighted(cat, w1, w2, w3_2s10s)
            blk = raw_w.iloc[sl]
        elif letter == "F":
            wc = float(row["w_cot"]) if pd.notna(row["w_cot"]) else 0.5
            we = float(row["w_etf"]) if pd.notna(row["w_etf"]) else 0.5
            raw_w = raw_f_weighted(cat, wc, we)
            blk = raw_w.iloc[sl]
        else:
            blk = cat[f"raw_{letter}"].iloc[sl]
        d.iloc[sl] = discrete_deadband(blk, tau).to_numpy(dtype=float, copy=False)
    return d


def apply_latest_tuning_overlays(cat: pd.DataFrame, cfg: Settings, run_dir: Path) -> None:
    """Mutates ``cat``: ``dir_*``, ``dir_*_raw``, and ``tuned_dir_<leg_id>`` for attach_consensus."""
    leg_df = pd.read_csv(run_dir / "per_leg_per_step.csv")
    cat_df = pd.read_csv(run_dir / "per_category_per_step.csv")
    tau_lu = _leg_tau_lookup(leg_df)
    bounds = iter_wf_step_bounds(len(cat), cfg)
    thr = float(cfg.threshold)

    for letter in sorted(cat_df["category"].astype(str).unique()):
        if letter == "G" and not cfg.include_gpr:
            continue
        col = f"dir_{letter}"
        if col not in cat.columns:
            continue
        d = _apply_category_block(cat, bounds, cat_df, letter, thr)
        cat[col] = d
        raw_col = f"dir_{letter}_raw"
        if raw_col in cat.columns:
            cat[raw_col] = d

    for leg_id in sorted(leg_df["leg_id"].astype(str).unique()):
        zc = f"subz_{leg_id}"
        if zc not in cat.columns:
            continue
        cat[f"tuned_dir_{leg_id}"] = leg_direction_with_csv_taus(
            cat[zc], bounds, leg_id, tau_lu, thr
        )
