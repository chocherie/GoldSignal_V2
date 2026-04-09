"""Non-overlapping OOS walk-forward steps (IS / OOS / step in trading days)."""

from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from gold_signal.config import Settings, settings
from gold_signal.tuning.wf_steps import iter_wf_step_bounds, wf_warmup_days


def _sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 5 or r.std() == 0:
        return float("nan")
    return float(np.sqrt(252) * r.mean() / r.std())


def annualized_sharpe(r: pd.Series) -> float:
    """Full-sample Sharpe (sqrt(252) * mean/std), NaN if undefined."""
    return _sharpe(r)


def cagr_pct_from_equity_multiple(multiple: float, n_trading_days: int) -> float:
    """Geometric annualized return (%) from ending equity multiple and span in trading days."""
    if n_trading_days < 2 or multiple <= 0 or not math.isfinite(multiple):
        return float("nan")
    return float((multiple ** (252.0 / n_trading_days) - 1.0) * 100.0)


def full_sample_return_stats(
    daily_returns: pd.Series,
    *,
    active_mask: pd.Series | None = None,
) -> dict:
    """
    Full-sample stats on daily strategy/benchmark returns (aligned index, NaNs → 0 for compounding).

    ``total_return_pct`` is CAGR (%), not cumulative holding-period return.
    ``volatility_annualized`` is annualized daily vol as **percentage points** (e.g. 16.0 → 16%),
    consistent with ``max_drawdown_pct`` and ``fmtPct`` in the UI.
    """
    r = daily_returns.fillna(0.0)
    n = len(r)
    if n == 0:
        return {
            "annualized_sharpe": None,
            "total_return_pct": None,
            "max_drawdown_pct": None,
            "volatility_annualized": None,
            "hit_ratio_all_days_pct": None,
            "trading_days": 0,
        }
    eq = equity_curve(r)
    peak = eq.cummax()
    dd = float(((eq / peak) - 1.0).min() * 100.0)
    vol = float(r.std() * np.sqrt(252) * 100.0) if n > 1 else float("nan")
    hit_all = float((r > 0).sum() / n * 100.0)
    mult = float(eq.iloc[-1])
    tot = cagr_pct_from_equity_multiple(mult, n)
    sharp = annualized_sharpe(r)
    out = {
        "annualized_sharpe": float(sharp) if sharp == sharp else None,
        "total_return_pct": float(tot) if tot == tot and not math.isnan(tot) else None,
        "max_drawdown_pct": dd if dd == dd else None,
        "volatility_annualized": vol if vol == vol and not math.isnan(vol) else None,
        "hit_ratio_all_days_pct": hit_all,
        "trading_days": int(n),
    }
    if active_mask is not None and len(active_mask):
        am = active_mask.reindex(r.index).fillna(False).astype(bool)
        if bool(am.any()):
            ra = r.loc[am]
            na = int(am.sum())
            if na > 0:
                out["hit_ratio_active_days_pct"] = float((ra > 0).sum() / na * 100.0)
                out["active_trading_days"] = na
    return out


def daily_versus_benchmark(strat_r: pd.Series, bench_r: pd.Series) -> dict:
    """Day-by-day comparison on common index (filled with 0)."""
    a = strat_r.fillna(0.0).align(bench_r.fillna(0.0), join="inner")
    s, b = a[0], a[1]
    n = len(s)
    if n < 2:
        return {"pct_days_strategy_return_gt_benchmark": None, "correlation": None, "days_compared": n}
    gt = float((s > b).sum() / n * 100.0)
    corr = float(np.corrcoef(s.values, b.values)[0, 1]) if n > 2 and s.std() > 0 and b.std() > 0 else float("nan")
    return {
        "pct_days_strategy_return_gt_benchmark": gt,
        "correlation": float(corr) if corr == corr else None,
        "days_compared": int(n),
    }


def oos_sharpe_vs_buy_hold_summary(steps: list[dict]) -> dict:
    """Counts WF OOS windows where strategy Sharpe exceeds buy-hold Sharpe (finite pairs only)."""
    n = 0
    beat = 0
    beat_lo = 0
    n_lo = 0
    for st in steps:
        sv = st.get("oos_sharpe")
        bv = st.get("oos_sharpe_buy_hold")
        if sv == sv and bv == bv:
            n += 1
            if float(sv) > float(bv):
                beat += 1
        lv = st.get("oos_sharpe_long_only")
        if lv == lv and bv == bv:
            n_lo += 1
            if float(lv) > float(bv):
                beat_lo += 1
    return {
        "oos_steps_compared": n,
        "oos_sharpe_beat_buy_hold_count": beat,
        "oos_sharpe_beat_buy_hold_pct": float(beat / n * 100.0) if n else None,
        "oos_long_only_steps_compared": n_lo,
        "oos_long_only_sharpe_beat_buy_hold_count": beat_lo,
        "oos_long_only_sharpe_beat_buy_hold_pct": float(beat_lo / n_lo * 100.0) if n_lo else None,
    }


def walk_forward_report(
    strat_returns: pd.Series,
    cfg: Settings | None = None,
    *,
    warmup_days: int | None = None,
) -> dict:
    """
    Split timeline into [warmup .. end] then consecutive OOS windows of wf_oos_days
    stepped by wf_step_days. Reports mean OOS Sharpe and per-step metrics.
    """
    cfg = cfg or settings
    is_d, oos_d, step_d = cfg.wf_is_days, cfg.wf_oos_days, cfg.wf_step_days
    warm = warmup_days if warmup_days is not None else wf_warmup_days(cfg)
    s = strat_returns.dropna()
    idx = s.index
    if len(idx) < warm + oos_d + 5:
        return {
            "n_steps": 0,
            "mean_oos_sharpe": None,
            "steps": [],
            "warmup_days": warm,
            "message": "insufficient history for walk-forward",
        }

    steps = []
    for b in iter_wf_step_bounds(len(idx), cfg):
        oos_slice = s.iloc[b.oos_start : b.oos_end]
        is_slice = s.iloc[b.is_start : b.is_end]
        steps.append(
            {
                "oos_start": str(oos_slice.index[0].date()),
                "oos_end": str(oos_slice.index[-1].date()),
                "oos_sharpe": _sharpe(oos_slice),
                "is_sharpe": _sharpe(is_slice) if len(is_slice) > 5 else float("nan"),
            }
        )

    sharps = [st["oos_sharpe"] for st in steps if st["oos_sharpe"] == st["oos_sharpe"]]
    mean_s = float(np.nanmean(sharps)) if sharps else None
    n_all = len(steps)
    cap_raw = os.environ.get("GOLD_WF_MAX_STEPS", "").strip()
    if cap_raw:
        cap = int(cap_raw)
        steps_out = steps[:cap]
        truncated = n_all > cap
    else:
        steps_out = steps
        truncated = False
    return {
        "n_steps": n_all,
        "mean_oos_sharpe": mean_s,
        "steps": steps_out,
        "truncated": truncated,
        "steps_in_payload": len(steps_out),
        "wf_is_days": is_d,
        "wf_oos_days": oos_d,
        "wf_step_days": step_d,
        "warmup_days": warm,
        "sharpe_methodology": {
            "oos_trading_days_per_window": oos_d,
            "is_trading_days_per_window": is_d,
            "step_trading_days": step_d,
            "mean_oos_sharpe": (
                "Arithmetic mean of √(252)×(mean/σ) computed inside each OOS window only "
                "(each window is wf_oos_days consecutive daily returns, stepped forward by wf_step_days)."
            ),
            "full_sample_sharpe": (
                "One √(252)×(mean/σ) over all daily returns in the merged backtest span."
            ),
            "why_they_differ": (
                "Mean OOS Sharpe averages short-window estimates (vol differs each slice); "
                "full-sample Sharpe is one long-horizon ratio. A higher mean OOS (e.g. ~0.83) vs lower "
                "full-sample (~0.67) often reflects stronger recent OOS windows or the fact that "
                "averaging window Sharpes is not the same as Sharpe of the concatenated series."
            ),
        },
    }


def equity_curve(strat_returns: pd.Series) -> pd.Series:
    return (1.0 + strat_returns.fillna(0.0)).cumprod()


def downsample_equity_points(items: list[dict], max_n: int) -> list[dict]:
    """Evenly spaced indices including first and last (for chart JSON size)."""
    n = len(items)
    if n <= max_n or n < 2:
        return items
    k = max_n
    idxs = sorted({int(round(i * (n - 1) / (k - 1))) for i in range(k)})
    return [items[i] for i in idxs]


def _direction_mix_pct(d: pd.Series) -> dict[str, float]:
    nobs = max(len(d), 1)
    di = d.fillna(0.0).round().clip(-1, 1).astype(int)
    return {
        "long": float((di == 1).sum() / nobs * 100.0),
        "short": float((di == -1).sum() / nobs * 100.0),
        "neutral": float((di == 0).sum() / nobs * 100.0),
    }


def _long_only_book_mix(d: pd.Series) -> dict[str, float]:
    """% sessions with long gold exposure vs flat (short signals become flat)."""
    nobs = max(len(d), 1)
    di = d.fillna(0.0).round().clip(-1, 1).astype(int)
    return {
        "long": float((di == 1).sum() / nobs * 100.0),
        "short": 0.0,
        "neutral": float((di != 1).sum() / nobs * 100.0),
    }


def equity_backtest_block(
    sr: pd.Series,
    sig: pd.DataFrame,
    mix_d: pd.Series,
    *,
    start: int,
    max_points: int,
    cfg: Settings | None = None,
    book_mix_long_only: bool = False,
    lightweight: bool = False,
) -> dict:
    """Walk-forward, Sharpe, return, equity curve, direction mix — shared by full vs long-only lanes.

    If ``lightweight=True``, skip walk-forward computation and equity curve to save memory.
    Used for per-subsignal backtests on memory-constrained hosts.
    """
    cfg = cfg or settings
    n = len(sig)
    eq = equity_curve(sr)
    fulleq = float(eq.iloc[-1]) if n else 1.0
    mix = _long_only_book_mix(mix_d) if book_mix_long_only else _direction_mix_pct(mix_d)
    cagr = cagr_pct_from_equity_multiple(fulleq, n) if n > 1 else float("nan")

    if lightweight:
        # Skip walk-forward and equity curve to save memory on constrained hosts.
        # Only compute full-sample Sharpe and CAGR.
        return {
            "walk_forward": {"n_steps": 0, "mean_oos_sharpe": None},
            "sharpe_full_sample": annualized_sharpe(sr),
            "equity_end_multiple": fulleq,
            "total_return_pct": float(cagr) if cagr == cagr and not math.isnan(cagr) else None,
            "direction_mix_pct": mix,
            "equity_tail_rebased": [],
        }

    s0 = float(eq.iloc[start]) if n > start else 1.0
    s0 = s0 if s0 else 1.0
    tail_curve = [
        {"d": str(sig.index[i].date()), "e": float(eq.iloc[i] / s0)}
        for i in range(start, n)
    ]
    tail_curve = downsample_equity_points(tail_curve, max_points)
    wf = walk_forward_report(sr, cfg)
    return {
        "walk_forward": wf,
        "sharpe_full_sample": annualized_sharpe(sr),
        "equity_end_multiple": fulleq,
        "total_return_pct": float(cagr) if cagr == cagr and not math.isnan(cagr) else None,
        "direction_mix_pct": mix,
        "equity_tail_rebased": tail_curve,
    }


def per_category_backtests(
    sig: pd.DataFrame,
    letters: list[str],
    *,
    tail: int | None = None,
    max_points: int = 1200,
    cfg: Settings | None = None,
) -> dict[str, dict]:
    """
    For each category L: walk-forward on strat_return_L, full-sample Sharpe, direction mix,
    rebased equity over the same window as the main chart (full sample if tail is None),
    downsampled to max_points for the API.
    """
    cfg = cfg or settings
    n = len(sig)
    start = 0 if tail is None else max(0, n - tail)
    out: dict[str, dict] = {}
    for L in letters:
        ccol = f"strat_return_{L}"
        clo = f"strat_return_{L}_long_only"
        dcol = f"dir_{L}"
        if ccol not in sig.columns or dcol not in sig.columns:
            continue
        sr = sig[ccol]
        d = sig[dcol]
        base = equity_backtest_block(
            sr, sig, d, start=start, max_points=max_points, cfg=cfg, book_mix_long_only=False
        )
        out[L] = base
        if clo in sig.columns:
            out[L]["long_only"] = equity_backtest_block(
                sig[clo],
                sig,
                d,
                start=start,
                max_points=max_points,
                cfg=cfg,
                book_mix_long_only=True,
            )
    return out


def per_subsignal_backtests(
    sig: pd.DataFrame,
    *,
    max_points: int = 400,
    cfg: Settings | None = None,
) -> dict[str, dict]:
    """
    Solo backtest each raw leg: sign(sub-z) lagged × XAUUSD (columns strat_sub_<id>).
    """
    from gold_signal.signals.subsignal_meta import SUBSIGNAL_META
    from gold_signal.signals.transforms import discrete_from_z

    cfg = cfg or settings
    n = len(sig)
    start = 0
    out: dict[str, dict] = {}
    for cname in sig.columns:
        if not cname.startswith("strat_sub_"):
            continue
        sid = cname[len("strat_sub_") :]
        zcol = f"subz_{sid}"
        if zcol not in sig.columns:
            continue
        sr = sig[cname]
        clo = f"strat_sub_{sid}_long_only"
        d = discrete_from_z(sig[zcol], cfg.threshold)
        di = d.fillna(0.0).round().clip(-1, 1).astype(int)
        meta = SUBSIGNAL_META.get(sid, {})
        # Use lightweight mode to reduce memory on constrained hosts (Render free tier)
        lite = os.environ.get("GOLD_LIGHTWEIGHT_SUBSIGNAL", "1").strip().lower() in ("1", "true", "yes")
        base = equity_backtest_block(
            sr, sig, di, start=start, max_points=max_points, cfg=cfg,
            book_mix_long_only=False, lightweight=lite,
        )
        out[sid] = {
            "id": sid,
            "label": meta.get("label", sid),
            "category": meta.get("category", sid.split("_", 1)[0] if "_" in sid else ""),
            **base,
        }
        if clo in sig.columns:
            out[sid]["long_only"] = equity_backtest_block(
                sig[clo],
                sig,
                di,
                start=start,
                max_points=max_points,
                cfg=cfg,
                book_mix_long_only=True,
                lightweight=lite,
            )
    return out
