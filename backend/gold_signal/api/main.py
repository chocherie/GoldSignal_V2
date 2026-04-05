"""FastAPI: health, latest signals, walk-forward summary, equity series."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from contextlib import asynccontextmanager

import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from gold_signal.backtest.walk_forward import (
    daily_versus_benchmark,
    downsample_equity_points,
    equity_backtest_block,
    equity_curve,
    full_sample_return_stats,
    oos_sharpe_vs_buy_hold_summary,
    per_category_backtests,
    per_subsignal_backtests,
    walk_forward_report,
)
from gold_signal.config import settings
from gold_signal.etl.panel import load_raw_panel
from gold_signal.jsonutil import sanitize
from gold_signal.signals.categories import build_signal_table
from gold_signal.signals.category_info import CATEGORY_INFO
from gold_signal.signals.subsignal_meta import SUBSIGNAL_META
from gold_signal.signals.tuned_overlays import resolve_tuning_run_dir, tuning_run_mtime

log = logging.getLogger("gold_signal.api")

_cache: tuple | None = None
_cache_key: tuple[float, float] | None = None


def _data_dir() -> Path:
    return settings.resolved_data_dir()


def _strategy_payload() -> dict:
    tr = resolve_tuning_run_dir(settings)
    return {
        "source": "tuned" if tr is not None else "production",
        "tuning_run_dir": str(tr) if tr is not None else None,
        "tuning_run_name": tr.name if tr is not None else None,
        "use_latest_tuning": bool(settings.use_latest_tuning),
    }


def _cache_invalidation_key() -> tuple[float, float]:
    data_dir = _data_dir()
    im = data_dir / "intermarket.csv"
    mt_data = im.stat().st_mtime if im.is_file() else 0.0
    tr = resolve_tuning_run_dir(settings)
    mt_tune = tuning_run_mtime(tr)
    return (mt_data, mt_tune)


def get_signal_frame():
    """Load panel and rebuild signals; cache invalidates when data or tuning-run CSV mtime changes."""
    global _cache, _cache_key
    key = _cache_invalidation_key()
    if _cache is not None and _cache_key == key:
        return _cache
    data_dir = _data_dir()
    panel, meta = load_raw_panel(data_dir, settings)
    sig = build_signal_table(panel, settings)
    _cache = (panel, meta, sig)
    _cache_key = key
    return _cache


def clear_signal_cache() -> None:
    global _cache, _cache_key
    _cache = None
    _cache_key = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_signal_frame()
    except FileNotFoundError:
        pass
    yield
    clear_signal_cache()


app = FastAPI(title="Gold Signal API", version="0.2.0", lifespan=lifespan)

_origins = os.environ.get("GOLD_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _NoStoreApiMiddleware(BaseHTTPMiddleware):
    """Avoid stale JSON behind browsers / CDNs when the UI is hosted separately from the API."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


app.add_middleware(_NoStoreApiMiddleware)


@app.get("/health")
def health():
    data_dir = _data_dir()
    ok = (data_dir / "intermarket.csv").is_file() and (data_dir / "gold_price.csv").is_file()
    tr = resolve_tuning_run_dir(settings)
    return sanitize(
        {
            "status": "ok" if ok else "degraded",
            "data_dir": str(data_dir),
            "strategy_source": "tuned" if tr is not None else "production",
            "tuning_run": tr.name if tr is not None else None,
        }
    )


@app.get("/api/v1/meta")
def meta():
    try:
        panel, m, sig = get_signal_frame()
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    return sanitize(
        {
            "as_of_utc": m.get("as_of_utc"),
            "warnings": m.get("warnings", []),
            "date_range": {
                "start": str(panel.index.min().date()) if len(panel) else None,
                "end": str(panel.index.max().date()) if len(panel) else None,
            },
            "rows": len(panel),
            "z_threshold": float(settings.threshold),
            "strategy": _strategy_payload(),
        }
    )


@app.get("/api/v1/signals/latest")
def signals_latest():
    try:
        panel, m, sig = get_signal_frame()
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    if sig.empty:
        raise HTTPException(503, detail="empty signal table")
    try:
        last = sig.iloc[-1]
        prev = sig.iloc[-2] if len(sig) > 1 else last
        letters = ["A", "B", "C", "D", "F"]
        if settings.include_gpr:
            letters.append("G")
        cats = []
        for L in letters:
            rv = last[f"dir_{L}"]
            rz = last[f"raw_{L}"]
            rc = last[f"conf_{L}"]
            meta = CATEGORY_INFO.get(L, {})
            cats.append(
                {
                    "id": L,
                    "direction": (int(round(float(rv))) if rv == rv else 1),
                    "confidence": (float(rc) if rc == rc else None),
                    "raw_score": (float(rz) if rz == rz else None),
                    "title": meta.get("title", f"Category {L}"),
                    "subtitle": meta.get("subtitle", ""),
                    "detail": meta.get("detail", ""),
                }
            )
        cd = last["consensus_dir"]
        cc = last["consensus_conf"]
        signal_legs = []
        for sid in sorted(SUBSIGNAL_META.keys()):
            if sid.startswith("G_") and not settings.include_gpr:
                continue
            zc = f"subz_{sid}"
            if zc not in sig.columns:
                continue
            zv = last[zc]
            rz = float(zv) if zv == zv else None
            sd_col = f"subsignal_dir_{sid}"
            if sd_col in sig.columns:
                dv = last[sd_col]
                if dv == dv:
                    direction = int(round(float(dv)))
                    if direction not in (-1, 0, 1):
                        direction = 1 if direction > 0 else -1
                elif rz is None:
                    direction = 1
                elif rz > 0:
                    direction = 1
                elif rz < 0:
                    direction = -1
                else:
                    direction = 1
            elif rz is None:
                direction = 1
            elif rz > 0:
                direction = 1
            elif rz < 0:
                direction = -1
            else:
                direction = 1
            meta = SUBSIGNAL_META[sid]
            signal_legs.append(
                {
                    "id": sid,
                    "category": meta["category"],
                    "label": meta["label"],
                    "raw_score": rz,
                    "direction": direction,
                }
            )
        payload = {
            "date": str(sig.index[-1].date()),
            "consensus": {
                "direction": (int(round(float(cd))) if cd == cd else 1),
                "confidence": (float(cc) if cc == cc else None),
            },
            "categories": cats,
            "signal_legs": signal_legs,
            "prev_date": str(sig.index[-2].date()) if len(sig) > 1 else None,
            "prev_consensus": int(round(float(prev["consensus_dir"]))) if len(sig) > 1 else None,
            "warnings": m.get("warnings", []),
            "strategy": _strategy_payload(),
        }
        return sanitize(payload)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("signals/latest failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _backtest_walk_forward_payload():
    try:
        panel, m, sig = get_signal_frame()
    except FileNotFoundError as e:
        raise HTTPException(503, detail=str(e)) from e
    rep = walk_forward_report(sig["strat_return"], settings)
    rep_lo = walk_forward_report(sig["strat_return_long_only"], settings)
    rep["mean_oos_sharpe_long_only"] = rep_lo.get("mean_oos_sharpe")
    for i, st in enumerate(rep["steps"]):
        los = rep_lo.get("steps") or []
        if i < len(los):
            st["oos_sharpe_long_only"] = los[i]["oos_sharpe"]
            st["is_sharpe_long_only"] = los[i]["is_sharpe"]
    bh = panel["xauusd"].pct_change(fill_method=None).reindex(sig.index).fillna(0.0)
    rep_bh = walk_forward_report(bh, settings)
    rep["mean_oos_sharpe_buy_hold"] = rep_bh.get("mean_oos_sharpe")
    for i, st in enumerate(rep["steps"]):
        bhs = rep_bh.get("steps") or []
        if i < len(bhs):
            st["oos_sharpe_buy_hold"] = bhs[i]["oos_sharpe"]
            st["is_sharpe_buy_hold"] = bhs[i]["is_sharpe"]
    rep["oos_vs_buy_hold"] = oos_sharpe_vs_buy_hold_summary(rep["steps"])

    active_ls = sig["consensus_dir"].shift(1).fillna(0.0).abs() > 0
    active_long_only_book = sig["consensus_dir"].shift(1).fillna(0.0) > 0
    full_sample_stats = {
        "consensus_long_short": full_sample_return_stats(
            sig["strat_return"], active_mask=active_ls
        ),
        "consensus_long_only": full_sample_return_stats(
            sig["strat_return_long_only"], active_mask=active_long_only_book
        ),
        "buy_hold_xauusd": full_sample_return_stats(bh, active_mask=None),
        "versus_buy_hold_daily": daily_versus_benchmark(sig["strat_return"], bh),
    }
    eq = equity_curve(sig["strat_return"])
    eq_lo = equity_curve(sig["strat_return_long_only"])
    bh_eq = equity_curve(bh)
    # Full-sample chart (downsampled for payload size). Rebased to 1.0 at first bar so
    # strategy vs buy-hold share a comparable scale over the whole history.
    chart_max_pts = int(os.environ.get("GOLD_CHART_MAX_POINTS", "1400"))
    cat_max_pts = int(os.environ.get("GOLD_CATEGORY_CHART_MAX_POINTS", "1200"))
    sub_max_pts = int(os.environ.get("GOLD_SUB_CHART_MAX_POINTS", "400"))
    start = 0
    s0 = float(eq.iloc[start]) if len(eq) else 1.0
    l0 = float(eq_lo.iloc[start]) if len(eq_lo) else 1.0
    b0 = float(bh_eq.iloc[start]) if len(bh_eq) else 1.0
    s0 = s0 if s0 else 1.0
    l0 = l0 if l0 else 1.0
    b0 = b0 if b0 else 1.0
    curve_full: list[dict] = []
    for i in range(start, len(eq)):
        curve_full.append(
            {
                "d": str(sig.index[i].date()),
                "s": float(eq.iloc[i] / s0),
                "l": float(eq_lo.iloc[i] / l0),
                "b": float(bh_eq.iloc[i] / b0),
            }
        )
    curve = downsample_equity_points(curve_full, chart_max_pts)
    first_oos = rep["steps"][0]["oos_start"] if rep.get("steps") else None
    equity_meta = {
        "chart_first_date": curve[0]["d"] if curve else None,
        "chart_last_date": curve[-1]["d"] if curve else None,
        "panel_start": str(panel.index.min().date()) if len(panel) else None,
        "panel_end": str(panel.index.max().date()) if len(panel) else None,
        "n_points": len(curve),
        "n_bars_full": len(curve_full),
        "wf_first_oos": first_oos,
        "hint": (
            "Plotted equity is the full merged history, evenly downsampled. "
            "First WF OOS is later than panel start due to in-sample warmup (~630 trading days). "
            "Sparse inputs (e.g. COT) still map to a long/short vote via sign(z); missing z defaults to long."
        ),
    }
    letters_bt = ["A", "B", "C", "D", "F"]
    if settings.include_gpr:
        letters_bt.append("G")
    cat_bt = per_category_backtests(
        sig, letters_bt, tail=None, max_points=cat_max_pts, cfg=settings
    )
    sub_bt = per_subsignal_backtests(sig, max_points=sub_max_pts, cfg=settings)

    mix_bh = pd.Series(1.0, index=sig.index)
    buy_hold_bt = equity_backtest_block(
        bh,
        sig,
        mix_bh,
        start=start,
        max_points=cat_max_pts,
        cfg=settings,
        book_mix_long_only=False,
    )
    buy_hold_bt["equity_tail_rebased_sub"] = equity_backtest_block(
        bh,
        sig,
        mix_bh,
        start=start,
        max_points=sub_max_pts,
        cfg=settings,
        book_mix_long_only=False,
    )["equity_tail_rebased"]

    return sanitize(
        {
            "walk_forward": rep,
            "full_sample_stats": full_sample_stats,
            "buy_hold_backtest": buy_hold_bt,
            "buy_hold_equity_end": float(bh_eq.iloc[-1]) if len(bh_eq) else None,
            "strategy_equity_end": float(eq.iloc[-1]) if len(eq) else None,
            "strategy_equity_end_long_only": float(eq_lo.iloc[-1]) if len(eq_lo) else None,
            "equity_curve_tail": curve,
            "equity_meta": equity_meta,
            "category_backtests": cat_bt,
            "subsignal_backtests": sub_bt,
            "warnings": m.get("warnings", []),
        }
    )


# Shorter path avoids some proxy stacks mishandling multi-segment routes; keep both.
@app.get("/api/v1/walk-forward")
def walk_forward_short():
    return _backtest_walk_forward_payload()


@app.get("/api/v1/backtest/walk-forward")
def backtest_walk_forward():
    return _backtest_walk_forward_payload()


@app.post("/api/v1/cache/invalidate")
def invalidate_cache():
    clear_signal_cache()
    return {"ok": True}
