"""Stage-1 category scores (plan defaults: A–F, optional G)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from gold_signal.config import Settings, settings
from gold_signal.signals.transforms import (
    confidence_series_from_z,
    discrete_from_z,
    log_return,
    macd_histogram,
    rolling_z,
    rsi,
)
from gold_signal.signals.tuned_overlays import apply_latest_tuning_overlays, resolve_tuning_run_dir


def _nanmean_row(df: pd.DataFrame) -> pd.Series:
    return df.mean(axis=1, skipna=True)


def compute_category_raw_scores(panel: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    cfg = cfg or settings
    w, zc, thr = cfg.z_window, cfg.z_clip, cfg.threshold
    out = pd.DataFrame(index=panel.index)

    close = panel["gc1_close"]
    # --- A: technical (GC1 + curve) ---
    lr5 = log_return(close, 5)
    lr20 = log_return(close, 20)
    lr60 = log_return(close, 60)
    z_lr5 = rolling_z(lr5, w, zc)
    z_lr20 = rolling_z(lr20, w, zc)
    z_lr60 = rolling_z(lr60, w, zc)
    z_mom = _nanmean_row(pd.DataFrame({"a": z_lr5, "b": z_lr20, "c": z_lr60}))
    r = rsi(close, 14)
    z_rsi = rolling_z((r - 50).astype(float), w, zc)
    z_macd = rolling_z(macd_histogram(close), w, zc)
    oi = panel.get("gc1_open_interest")
    if oi is not None and oi.notna().any():
        oi_pct = oi.pct_change(5, fill_method=None)
        z_oi = rolling_z(oi_pct.replace([np.inf, -np.inf], np.nan), w, zc)
    else:
        z_oi = pd.Series(np.nan, index=panel.index)
    g2 = panel.get("gc2_price")
    if g2 is not None and g2.notna().any():
        curve = np.log(g2 / close.replace(0, np.nan))
        z_curve = rolling_z(curve.diff(20), w, zc)
        gc12 = (close - g2).astype(float)
        z_gc12 = rolling_z(gc12.diff(20), w, zc)
    else:
        z_curve = pd.Series(np.nan, index=panel.index)
        z_gc12 = pd.Series(np.nan, index=panel.index)

    def _z_level_or_nan(col: str) -> pd.Series:
        s = panel.get(col)
        if s is None or not s.notna().any():
            return pd.Series(np.nan, index=panel.index)
        return rolling_z(s.diff(20), w, zc)

    z_lease = _z_level_or_nan("GOLD_LEASE")
    z_in_prem = _z_level_or_nan("GOLD_INDIA_PREM")
    z_cn_prem = _z_level_or_nan("GOLD_CHINA_PREM")
    z_cb = _z_level_or_nan("GOLD_CB_HOLDINGS")
    z_cn_imp = _z_level_or_nan("GOLD_CHINA_IMPORT")
    z_in_imp = _z_level_or_nan("GOLD_INDIA_IMPORT")

    raw_a = _nanmean_row(
        pd.DataFrame(
            {
                "m": z_mom,
                "r": z_rsi,
                "d": z_macd,
                "o": z_oi,
                "c": z_curve,
                "g": z_gc12,
                "l": z_lease,
                "i": z_in_prem,
                "h": z_cn_prem,
                "b": z_cb,
                "ci": z_cn_imp,
                "ii": z_in_imp,
            }
        )
    )
    out["subz_A_mom_5d"] = z_lr5
    out["subz_A_mom_20d"] = z_lr20
    out["subz_A_mom_60d"] = z_lr60
    out["subz_A_rsi"] = z_rsi
    out["subz_A_macd"] = z_macd
    out["subz_A_oi"] = z_oi
    out["subz_A_curve"] = z_curve
    out["subz_A_gc12_spread"] = z_gc12
    out["subz_A_lease"] = z_lease
    out["subz_A_india_prem"] = z_in_prem
    out["subz_A_china_prem"] = z_cn_prem
    out["subz_A_cb_holdings"] = z_cb
    out["subz_A_china_import"] = z_cn_imp
    out["subz_A_india_import"] = z_in_imp

    rv20 = close.pct_change(fill_method=None).rolling(20, min_periods=10).std()
    rv_med = rv20.rolling(w, min_periods=60).median()
    vol_scale = 1.0 / (1.0 + rv20 / rv_med.replace(0, np.nan))

    # --- B: rates + 2s10s (shadow column unused) ---
    tnx = panel.get("TNX")
    if tnx is None:
        tnx = pd.Series(np.nan, index=panel.index)
    d10 = tnx.diff(20)
    z_nom = rolling_z(-d10, w, zc)

    tips = panel.get("TIPS_REAL_10Y")
    be = panel.get("USGGBE10")
    if tips is not None and tips.notna().any():
        d_real = tips.diff(20)
    elif be is not None and be.notna().any():
        d_real = be.diff(20)
    else:
        d_real = pd.Series(np.nan, index=panel.index)
    z_real = rolling_z(-d_real, w, zc)

    sh = panel.get("shadow_rate")
    if sh is not None and sh.notna().any():
        z_shadow = rolling_z(-(sh.diff(20)), w, zc).fillna(0.0)
    else:
        z_shadow = pd.Series(0.0, index=panel.index)

    u2 = panel.get("USGG2YR")
    if u2 is not None and u2.notna().any():
        spr = tnx - u2
        z_curve_rates = rolling_z(-(spr.diff(20)), w, zc)
    else:
        z_curve_rates = pd.Series(np.nan, index=panel.index)

    raw_b = _nanmean_row(
        pd.DataFrame({"n": z_nom, "r": z_real, "s": z_shadow, "c": z_curve_rates})
    )
    out["subz_B_nom"] = z_nom
    out["subz_B_real"] = z_real
    out["subz_B_shadow"] = z_shadow
    out["subz_B_2s10s"] = z_curve_rates

    # --- C: USD ---
    dxy = panel.get("DXY")
    if dxy is not None and dxy.notna().any():
        dlx = np.log(dxy.replace(0, np.nan)).diff(20)
        raw_c = rolling_z(-dlx, w, zc)
    else:
        raw_c = pd.Series(np.nan, index=panel.index)
    out["subz_C_dxy"] = raw_c

    # --- D: risk (VIX log change) ---
    vix = panel.get("VIX")
    if vix is not None and vix.notna().any():
        lv = np.log(vix.replace(0, np.nan).clip(lower=1e-6))
        raw_d = rolling_z(lv.diff(20), w, zc)
    else:
        raw_d = pd.Series(np.nan, index=panel.index)
    out["subz_D_vix"] = raw_d

    # --- F: flow ---
    mm = panel.get("cot_managed_money_net")
    pr = panel.get("cot_producer_net")
    if mm is not None and mm.notna().any():
        z_mm = rolling_z(mm, w, zc)
    else:
        z_mm = pd.Series(np.nan, index=panel.index)
    if pr is not None and pr.notna().any():
        z_pr = rolling_z(pr, w, zc)
    else:
        z_pr = pd.Series(np.nan, index=panel.index)

    def _z_cot_net(col: str) -> pd.Series:
        s = panel.get(col)
        if s is None or not s.notna().any():
            return pd.Series(np.nan, index=panel.index)
        return rolling_z(s, w, zc)

    z_cot_other = _z_cot_net("cot_other_reportables_net")
    z_imm_legacy = _z_cot_net("cot_legacy_noncomm_net")
    z_cot = _nanmean_row(
        pd.DataFrame({"a": z_mm, "b": z_pr, "o": z_cot_other, "i": z_imm_legacy})
    )

    gl = panel.get("gld_shares_lagged")
    if gl is not None and gl.notna().any():
        fe = gl.pct_change(5, fill_method=None)
        z_etf = rolling_z(fe.replace([np.inf, -np.inf], np.nan), w, zc)
    else:
        z_etf = pd.Series(np.nan, index=panel.index)
    raw_f = _nanmean_row(pd.DataFrame({"cot": z_cot, "etf": z_etf}))
    out["subz_F_cot_mm"] = z_mm
    out["subz_F_cot_prod"] = z_pr
    out["subz_F_cot_other"] = z_cot_other
    out["subz_F_imm_legacy"] = z_imm_legacy
    out["subz_F_etf"] = z_etf

    # --- G: GPR optional ---
    gpr = panel.get("gpr_monthly")
    if cfg.include_gpr and gpr is not None and gpr.notna().any():
        dg = gpr.diff(3)
        raw_g = rolling_z(dg, max(w, 60), zc)
        out["subz_G_gpr"] = raw_g
    else:
        raw_g = pd.Series(np.nan, index=panel.index)

    out["raw_A"] = raw_a
    out["raw_B"] = raw_b
    out["raw_C"] = raw_c
    out["raw_D"] = raw_d
    out["raw_F"] = raw_f
    out["raw_G"] = raw_g
    out["vol_scale_A"] = vol_scale

    for letter in ("A", "B", "C", "D", "F"):
        rz = out[f"raw_{letter}"]
        out[f"dir_{letter}_raw"] = discrete_from_z(rz, thr)
        out[f"dir_{letter}"] = out[f"dir_{letter}_raw"]
        out[f"conf_{letter}"] = confidence_series_from_z(rz, thr)

    if cfg.include_gpr:
        out["dir_G_raw"] = discrete_from_z(out["raw_G"], thr)
        out["dir_G"] = out["dir_G_raw"]
        out["conf_G"] = confidence_series_from_z(out["raw_G"], thr)
    else:
        # G not in combiner; placeholder columns stay long-only for schema (not voted).
        out["dir_G"] = pd.Series(1.0, index=panel.index)
        out["conf_G"] = pd.Series(0.0, index=panel.index)

    out.loc[:, "conf_A"] = out["conf_A"] * out["vol_scale_A"].fillna(1.0)
    return out


def attach_consensus(cat: pd.DataFrame, panel: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    from gold_signal.signals.combiner import majority_combiner

    cfg = cfg or settings
    letters = ["A", "B", "C", "D", "F"]
    if cfg.include_gpr:
        letters.append("G")
    dirs = [cat[f"dir_{x}"] for x in letters]
    confs = [cat[f"conf_{x}"] for x in letters]
    comb = majority_combiner(dirs, confs, letters)
    raw_sum = pd.DataFrame({L: cat[f"raw_{L}"] for L in letters}).sum(axis=1, skipna=True).fillna(0.0)
    cd = comb["direction"].astype(float)
    tie = cd == 0.0
    tie_break = np.sign(raw_sum).replace(0.0, 1.0).astype(float)
    cat["consensus_dir_raw"] = cd.where(~tie, tie_break)
    cat["consensus_conf"] = comb["confidence"]
    cat["consensus_dir"] = cat["consensus_dir_raw"]

    r = panel["xauusd"].pct_change(fill_method=None)
    # Position timing: signal fixed at COB on calendar day T uses XAUUSD return close(T)→close(T+1),
    # i.e. one-session hold (entry COB T, exit COB T+1). Row index is the exit session; `shift(1)`
    # maps the signal decided at prior COB to that forward return. New signal at COB flips next day — no min-hold.
    lag = cat["consensus_dir"].shift(1)
    cat["strat_return"] = lag.fillna(0.0) * r.fillna(0.0)
    cat["strat_return_long_only"] = (
        cat["consensus_dir"].clip(lower=0.0).shift(1).fillna(0.0) * r.fillna(0.0)
    )

    # Per-category P&L: same 1-session XAUUSD rule as consensus.
    for L in letters:
        lag_l = cat[f"dir_{L}"].shift(1).fillna(0.0)
        cat[f"strat_return_{L}"] = lag_l * r.fillna(0.0)
        cat[f"strat_return_{L}_long_only"] = (
            cat[f"dir_{L}"].clip(lower=0.0).shift(1).fillna(0.0) * r.fillna(0.0)
        )

    # Per raw leg: discrete(sub-z) × T+1 XAUUSD (same discrete rule as category composite).
    thr = cfg.threshold
    for col in list(cat.columns):
        if not col.startswith("subz_"):
            continue
        sid = col[len("subz_") :]
        zs = cat[col]
        td = f"tuned_dir_{sid}"
        if td in cat.columns:
            d = cat[td]
        else:
            d = discrete_from_z(zs, thr)
        cat[f"subsignal_dir_{sid}"] = d
        cat[f"strat_sub_{sid}"] = d.shift(1).fillna(0.0) * r.fillna(0.0)
        cat[f"strat_sub_{sid}_long_only"] = (
            d.clip(lower=0.0).shift(1).fillna(0.0) * r.fillna(0.0)
        )

    return cat


def build_signal_table(panel: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    cfg = cfg or settings
    cat = compute_category_raw_scores(panel, cfg)
    run_dir = resolve_tuning_run_dir(cfg)
    if run_dir is not None:
        apply_latest_tuning_overlays(cat, cfg, run_dir)
    sig = attach_consensus(cat, panel, cfg)
    drop = [c for c in sig.columns if str(c).startswith("tuned_dir_")]
    if drop:
        sig = sig.drop(columns=drop)
    return sig.copy()
