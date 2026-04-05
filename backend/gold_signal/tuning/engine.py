"""Walk-forward grid search: IS Sharpe selection, OOS recording (research-only)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from gold_signal.backtest.walk_forward import _sharpe
from gold_signal.config import Settings, settings
from gold_signal.etl.panel import load_raw_panel
from gold_signal.signals.categories import compute_category_raw_scores
from gold_signal.signals.subsignal_meta import SUBSIGNAL_META
from gold_signal.signals.transforms import discrete_deadband
from gold_signal.tuning.constants import ABSTAIN_SUBLEG_IDS
from gold_signal.tuning.deflated_sharpe import deflated_sharpe_haircut, expected_sharpe_selection_bias
from gold_signal.tuning.horizon import (
    A_MOM_WEIGHT_TRIPLES,
    B_WEIGHT_QUADS,
    F_COT_ETF_WEIGHTS,
    raw_a_with_momentum_weights,
    raw_b_weighted,
    raw_f_weighted,
)
from gold_signal.tuning.wf_steps import WfStepBounds, iter_wf_step_bounds


def _strat_returns(direction: pd.Series, r: pd.Series) -> pd.Series:
    return direction.shift(1).fillna(0.0) * r.fillna(0.0)


def _turnover_is(direction: pd.Series, b: WfStepBounds) -> float:
    d = direction.iloc[b.is_start : b.is_end].astype(float)
    if len(d) < 2:
        return 0.0
    return float(d.diff().abs().sum())


def _tau_grid(n: int) -> list[float]:
    n = max(2, int(n))
    return [float(x) for x in np.linspace(0.0, 1.0, n)]


def _best_tau_on_raw(
    raw: pd.Series,
    r: pd.Series,
    b: WfStepBounds,
    taus: list[float],
) -> tuple[float, float, float, float]:
    """Returns tau_star, is_sharpe, oos_sharpe, is_turnover."""
    best_tau = taus[0]
    best_is = float("-inf")
    best_to = float("inf")
    for tau in taus:
        d = discrete_deadband(raw, tau)
        st = _strat_returns(d, r)
        isv = _sharpe(st.iloc[b.is_start : b.is_end])
        to = _turnover_is(d, b)
        if isv == isv:
            if isv > best_is or (isv == best_is and to < best_to) or (isv == best_is and to == best_to and tau < best_tau):
                best_is = isv
                best_tau = tau
                best_to = to
    if best_is == float("-inf"):
        best_is = float("nan")
    d_star = discrete_deadband(raw, best_tau)
    st = _strat_returns(d_star, r)
    oos = _sharpe(st.iloc[b.oos_start : b.oos_end])
    to_star = _turnover_is(d_star, b)
    return best_tau, best_is, oos, to_star


def _best_weights_then_tau(
    cat: pd.DataFrame,
    r: pd.Series,
    b: WfStepBounds,
    taus: list[float],
    weight_grid: list,
    raw_from_w,
) -> tuple[tuple, float, float, float, float, float]:
    """
    raw_from_w(w) -> raw Series.
    Returns (w_star, tau_star, is_sh_w, is_sh_final, oos_sh, n_w_trials).
    """
    best_w = weight_grid[0]
    best_is = float("-inf")
    for w in weight_grid:
        raw = raw_from_w(w)
        d = discrete_deadband(raw, 0.0)
        st = _strat_returns(d, r)
        isv = _sharpe(st.iloc[b.is_start : b.is_end])
        if isv == isv and isv > best_is:
            best_is = isv
            best_w = w
    if best_is == float("-inf"):
        best_is = float("nan")
    raw_star = raw_from_w(best_w)
    tau_star, is2, oos, _ = _best_tau_on_raw(raw_star, r, b, taus)
    return best_w, tau_star, best_is, is2, oos, float(len(weight_grid))


def run_wf_tune(
    out_dir: Path | None = None,
    cfg: Settings | None = None,
) -> Path:
    cfg = cfg or settings
    tau_n = int(os.environ.get("GOLD_TUNE_TAU_N", "11"))
    taus = _tau_grid(tau_n)

    data_dir = cfg.resolved_data_dir()
    panel, meta = load_raw_panel(data_dir, cfg)
    cat = compute_category_raw_scores(panel, cfg)
    r = panel["xauusd"].pct_change(fill_method=None).reindex(cat.index).fillna(0.0)

    n = len(cat)
    all_bounds = iter_wf_step_bounds(n, cfg)
    cap_raw = os.environ.get("GOLD_WF_MAX_STEPS", "").strip()
    if cap_raw:
        bounds = all_bounds[: int(cap_raw)]
    else:
        bounds = all_bounds

    if out_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = cfg.project_root / "data" / "tuning_runs" / ts
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    leg_rows: list[dict] = []
    cat_rows: list[dict] = []

    n_tau_trials = len(taus)

    for b in bounds:
        # --- per sub-leg ---
        for sid in sorted(SUBSIGNAL_META.keys()):
            if sid.startswith("G_") and not cfg.include_gpr:
                continue
            zc = f"subz_{sid}"
            if zc not in cat.columns:
                continue
            z = cat[zc]
            best_tau = taus[0]
            best_is = float("-inf")
            best_to = float("inf")
            for tau in taus:
                d = discrete_deadband(z, tau)
                st = _strat_returns(d, r)
                isv = _sharpe(st.iloc[b.is_start : b.is_end])
                to = _turnover_is(d, b)
                if isv == isv:
                    if isv > best_is or (isv == best_is and to < best_to) or (isv == best_is and to == best_to and tau < best_tau):
                        best_is = isv
                        best_tau = tau
                        best_to = to
            if best_is == float("-inf"):
                best_is = float("nan")
            d_star = discrete_deadband(z, best_tau)
            oos = _sharpe(_strat_returns(d_star, r).iloc[b.oos_start : b.oos_end])
            leg_rows.append(
                {
                    "step_idx": b.step_idx,
                    "oos_start_iloc": b.oos_start,
                    "leg_id": sid,
                    "tau_star": best_tau,
                    "is_sharpe": best_is,
                    "oos_sharpe": oos,
                    "n_trials": n_tau_trials,
                }
            )

        # --- category A ---
        def raw_a(w):
            return raw_a_with_momentum_weights(cat, w[0], w[1], w[2])

        w_star, tau_a, is_w, is_f, oos_a, n_w = _best_weights_then_tau(
            cat, r, b, taus, A_MOM_WEIGHT_TRIPLES, raw_a
        )
        cat_rows.append(
            {
                "step_idx": b.step_idx,
                "category": "A",
                "w5": w_star[0],
                "w20": w_star[1],
                "w60": w_star[2],
                "tau_star": tau_a,
                "is_sharpe_weights": is_w,
                "is_sharpe_final": is_f,
                "oos_sharpe": oos_a,
                "n_weight_trials": int(n_w),
                "n_tau_trials": n_tau_trials,
            }
        )

        # --- category B ---
        def raw_b(w):
            return raw_b_weighted(cat, w[0], w[1], w[2], w[3])

        w_star, tau_b, is_w, is_f, oos_b, n_w = _best_weights_then_tau(
            cat, r, b, taus, B_WEIGHT_QUADS, raw_b
        )
        cat_rows.append(
            {
                "step_idx": b.step_idx,
                "category": "B",
                "w1": w_star[0],
                "w2": w_star[1],
                "w3": w_star[2],
                "w4": w_star[3],
                "tau_star": tau_b,
                "is_sharpe_weights": is_w,
                "is_sharpe_final": is_f,
                "oos_sharpe": oos_b,
                "n_weight_trials": int(n_w),
                "n_tau_trials": n_tau_trials,
            }
        )

        # --- category F ---
        def raw_f(w):
            return raw_f_weighted(cat, w[0], w[1])

        w_star, tau_f, is_w, is_f, oos_f, n_w = _best_weights_then_tau(
            cat, r, b, taus, F_COT_ETF_WEIGHTS, raw_f
        )
        cat_rows.append(
            {
                "step_idx": b.step_idx,
                "category": "F",
                "w_cot": w_star[0],
                "w_etf": w_star[1],
                "tau_star": tau_f,
                "is_sharpe_weights": is_w,
                "is_sharpe_final": is_f,
                "oos_sharpe": oos_f,
                "n_weight_trials": int(n_w),
                "n_tau_trials": n_tau_trials,
            }
        )

        # --- C, D: τ only ---
        for letter, col in [("C", "raw_C"), ("D", "raw_D")]:
            raw = cat[col]
            tau_star, is_s, oos_s, _ = _best_tau_on_raw(raw, r, b, taus)
            cat_rows.append(
                {
                    "step_idx": b.step_idx,
                    "category": letter,
                    "tau_star": tau_star,
                    "is_sharpe_weights": None,
                    "is_sharpe_final": is_s,
                    "oos_sharpe": oos_s,
                    "n_weight_trials": 0,
                    "n_tau_trials": n_tau_trials,
                }
            )

        if cfg.include_gpr and "raw_G" in cat.columns:
            raw = cat["raw_G"]
            tau_star, is_s, oos_s, _ = _best_tau_on_raw(raw, r, b, taus)
            cat_rows.append(
                {
                    "step_idx": b.step_idx,
                    "category": "G",
                    "tau_star": tau_star,
                    "is_sharpe_weights": None,
                    "is_sharpe_final": is_s,
                    "oos_sharpe": oos_s,
                    "n_weight_trials": 0,
                    "n_tau_trials": n_tau_trials,
                }
            )

    pd.DataFrame(leg_rows).to_csv(out_dir / "per_leg_per_step.csv", index=False)
    pd.DataFrame(cat_rows).to_csv(out_dir / "per_category_per_step.csv", index=False)

    # Summary: mean OOS Sharpe per leg / category + haircut
    leg_df = pd.DataFrame(leg_rows)
    cat_df = pd.DataFrame(cat_rows)
    oos_d = cfg.wf_oos_days
    summary: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_steps": len(bounds),
        "wf_oos_days": cfg.wf_oos_days,
        "wf_is_days": cfg.wf_is_days,
        "tau_grid_points": n_tau_trials,
        "abstain_subleg_ids": sorted(ABSTAIN_SUBLEG_IDS),
        "discrete_deadband_nan_is_flat": True,
        "warnings": meta.get("warnings", []),
        "per_leg": {},
        "per_category": {},
    }

    if len(leg_df):
        for lid, g in leg_df.groupby("leg_id"):
            oos = g["oos_sharpe"].dropna()
            m = float(oos.mean()) if len(oos) else float("nan")
            summary["per_leg"][lid] = {
                "mean_oos_sharpe": m,
                "median_oos_sharpe": float(oos.median()) if len(oos) else None,
                "n_trials_per_step": n_tau_trials,
                "expected_selection_bias": expected_sharpe_selection_bias(n_tau_trials, oos_d),
                "deflated_sharpe_haircut": deflated_sharpe_haircut(m, n_tau_trials, oos_d),
            }

    if len(cat_df):
        for cname, g in cat_df.groupby("category"):
            oos = g["oos_sharpe"].dropna()
            m = float(oos.mean()) if len(oos) else float("nan")
            if cname in ("C", "D", "G"):
                n_tr = n_tau_trials
            else:
                nw = int(g["n_weight_trials"].max() or 0) if "n_weight_trials" in g.columns else 0
                n_tr = max(n_tau_trials, nw * n_tau_trials)
            summary["per_category"][cname] = {
                "mean_oos_sharpe": m,
                "median_oos_sharpe": float(oos.median()) if len(oos) else None,
                "n_trials_effective": n_tr,
                "expected_selection_bias": expected_sharpe_selection_bias(n_tr, oos_d),
                "deflated_sharpe_haircut": deflated_sharpe_haircut(m, n_tr, oos_d),
            }

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    return out_dir
