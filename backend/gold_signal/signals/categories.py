"""Stage-1 category scores — v3: raw-sign direction, abstention, contrarian COT, regime gate."""

from __future__ import annotations

import numpy as np
import pandas as pd

from gold_signal.config import Settings, settings
from gold_signal.signals.transforms import (
    confidence_series_from_z,
    discrete_from_raw,
    discrete_from_z,
    log_return,
    macd_histogram,
    rolling_z,
    rsi,
)
from gold_signal.signals.tuned_overlays import apply_latest_tuning_overlays, resolve_tuning_run_dir


def _nanmean_row(df: pd.DataFrame) -> pd.Series:
    return df.mean(axis=1, skipna=True)


# ---------------------------------------------------------------------------
# Signal classification: which signals use raw-sign vs level-z for direction.
# raw-sign  → direction = sign(raw_feature), z is for confidence only
# level-z   → direction = sign(z_level(feature))
# contrarian → direction = sign(-z_level(feature))
# ---------------------------------------------------------------------------
RAW_SIGN_SUBSIGNALS = {
    "A_mom_5d", "A_mom_20d", "A_mom_60d", "A_rsi", "A_macd", "A_oi",
    "A_curve", "A_gc12_spread", "A_lease", "A_india_prem", "A_china_prem",
    "A_cb_holdings", "A_china_import", "A_india_import", "A_gsr",
    "B_nom", "B_real", "B_2s10s", "B_cesi",
    "C_dxy",
    "D_vix", "D_gvz",
    "F_etf",
    "G_gpr",
}

CONTRARIAN_LEVEL_Z = {"F_cot_mm", "F_cot_other", "F_imm_legacy"}
TREND_LEVEL_Z = {"F_cot_prod"}


def compute_category_raw_scores(panel: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    cfg = cfg or settings
    w, zc, thr = cfg.z_window, cfg.z_clip, cfg.threshold
    out = pd.DataFrame(index=panel.index)

    close = panel["gc1_close"]

    # --- A: technical (GC1 + curve + physical overlays) ---
    # Raw features (pre-z) — kept for raw-sign direction
    raw_lr5 = log_return(close, 5)
    raw_lr20 = log_return(close, 20)
    raw_lr60 = log_return(close, 60)
    raw_rsi = (rsi(close, 14) - 50).astype(float)
    raw_macd = macd_histogram(close)

    oi = panel.get("gc1_open_interest")
    if oi is not None and oi.notna().any():
        raw_oi = oi.pct_change(5, fill_method=None).replace([np.inf, -np.inf], np.nan)
    else:
        raw_oi = pd.Series(np.nan, index=panel.index)

    g2 = panel.get("gc2_price")
    if g2 is not None and g2.notna().any():
        curve = np.log(g2 / close.replace(0, np.nan))
        raw_curve = curve.diff(20)
        gc12 = (close - g2).astype(float)
        raw_gc12 = gc12.diff(20)
    else:
        raw_curve = pd.Series(np.nan, index=panel.index)
        raw_gc12 = pd.Series(np.nan, index=panel.index)

    def _raw_diff20_or_nan(col: str) -> pd.Series:
        s = panel.get(col)
        if s is None or not s.notna().any():
            return pd.Series(np.nan, index=panel.index)
        return s.diff(20)

    raw_lease = _raw_diff20_or_nan("GOLD_LEASE")
    raw_in_prem = _raw_diff20_or_nan("GOLD_INDIA_PREM")
    raw_cn_prem = _raw_diff20_or_nan("GOLD_CHINA_PREM")
    raw_cb = _raw_diff20_or_nan("GOLD_CB_HOLDINGS")
    raw_cn_imp = _raw_diff20_or_nan("GOLD_CHINA_IMPORT")
    raw_in_imp = _raw_diff20_or_nan("GOLD_INDIA_IMPORT")

    si1 = panel.get("SI1")
    if si1 is not None and si1.notna().any():
        gsr = close / si1.replace(0, np.nan)
        raw_gsr = gsr.diff(20)
    else:
        raw_gsr = pd.Series(np.nan, index=panel.index)

    # Z-scores (for confidence and the category-level raw composite)
    z_lr5 = rolling_z(raw_lr5, w, zc)
    z_lr20 = rolling_z(raw_lr20, w, zc)
    z_lr60 = rolling_z(raw_lr60, w, zc)
    z_rsi = rolling_z(raw_rsi, w, zc)
    z_macd = rolling_z(raw_macd, w, zc)
    z_oi = rolling_z(raw_oi, w, zc)
    z_curve = rolling_z(raw_curve, w, zc)
    z_gc12 = rolling_z(raw_gc12, w, zc)
    z_lease = rolling_z(raw_lease, w, zc)
    z_in_prem = rolling_z(raw_in_prem, w, zc)
    z_cn_prem = rolling_z(raw_cn_prem, w, zc)
    z_cb = rolling_z(raw_cb, w, zc)
    z_cn_imp = rolling_z(raw_cn_imp, w, zc)
    z_in_imp = rolling_z(raw_in_imp, w, zc)
    z_gsr = rolling_z(raw_gsr, w, zc)

    z_mom = _nanmean_row(pd.DataFrame({"a": z_lr5, "b": z_lr20, "c": z_lr60}))

    raw_a = _nanmean_row(
        pd.DataFrame(
            {
                "m": z_mom, "r": z_rsi, "d": z_macd, "o": z_oi,
                "c": z_curve, "g": z_gc12,
                "l": z_lease, "i": z_in_prem, "h": z_cn_prem,
                "b": z_cb, "ci": z_cn_imp, "ii": z_in_imp,
                "gsr": z_gsr,
            }
        )
    )

    # Store sub-z (for confidence) and raw features (for direction)
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
    out["subz_A_gsr"] = z_gsr

    # Store raw feature values for raw-sign direction (Bug fix 1)
    out["raw_feat_A_mom_5d"] = raw_lr5
    out["raw_feat_A_mom_20d"] = raw_lr20
    out["raw_feat_A_mom_60d"] = raw_lr60
    out["raw_feat_A_rsi"] = raw_rsi
    out["raw_feat_A_macd"] = raw_macd
    out["raw_feat_A_oi"] = raw_oi
    out["raw_feat_A_curve"] = raw_curve
    out["raw_feat_A_gc12_spread"] = raw_gc12
    out["raw_feat_A_lease"] = raw_lease
    out["raw_feat_A_india_prem"] = raw_in_prem
    out["raw_feat_A_china_prem"] = raw_cn_prem
    out["raw_feat_A_cb_holdings"] = raw_cb
    out["raw_feat_A_china_import"] = raw_cn_imp
    out["raw_feat_A_india_import"] = raw_in_imp
    out["raw_feat_A_gsr"] = raw_gsr

    rv20 = close.pct_change(fill_method=None).rolling(20, min_periods=10).std()
    rv_med = rv20.rolling(w, min_periods=60).median()
    vol_scale = 1.0 / (1.0 + rv20 / rv_med.replace(0, np.nan))

    # --- B: rates + 2s10s (shadow removed in v3) ---
    tnx = panel.get("TNX")
    if tnx is None:
        tnx = pd.Series(np.nan, index=panel.index)
    d10 = tnx.diff(20)
    raw_nom = -d10  # negative sign: falling yields → bullish gold
    z_nom = rolling_z(raw_nom, w, zc)

    tips = panel.get("TIPS_REAL_10Y")
    be = panel.get("USGGBE10")
    if tips is not None and tips.notna().any():
        d_real = tips.diff(20)
    elif be is not None and be.notna().any():
        d_real = be.diff(20)
    else:
        d_real = pd.Series(np.nan, index=panel.index)
    raw_real = -d_real
    z_real = rolling_z(raw_real, w, zc)

    u2 = panel.get("USGG2YR")
    if u2 is not None and u2.notna().any():
        spr = tnx - u2
        raw_2s10s = -(spr.diff(20))
    else:
        raw_2s10s = pd.Series(np.nan, index=panel.index)
    z_curve_rates = rolling_z(raw_2s10s, w, zc)

    cesi = panel.get("CESI")
    if cesi is not None and cesi.notna().any():
        raw_cesi = -cesi  # negative: surprise below expectations → bullish gold
    else:
        raw_cesi = pd.Series(np.nan, index=panel.index)
    z_cesi = rolling_z(raw_cesi, w, zc)

    raw_b = _nanmean_row(pd.DataFrame({"n": z_nom, "r": z_real, "c": z_curve_rates, "e": z_cesi}))
    out["subz_B_nom"] = z_nom
    out["subz_B_real"] = z_real
    out["subz_B_2s10s"] = z_curve_rates
    out["subz_B_cesi"] = z_cesi
    out["raw_feat_B_nom"] = raw_nom
    out["raw_feat_B_real"] = raw_real
    out["raw_feat_B_2s10s"] = raw_2s10s
    out["raw_feat_B_cesi"] = raw_cesi

    # --- C: USD ---
    dxy = panel.get("DXY")
    if dxy is not None and dxy.notna().any():
        dlx = np.log(dxy.replace(0, np.nan)).diff(20)
        raw_dxy = -dlx  # negative: weaker USD → bullish gold
        raw_c = rolling_z(raw_dxy, w, zc)
    else:
        raw_dxy = pd.Series(np.nan, index=panel.index)
        raw_c = pd.Series(np.nan, index=panel.index)
    out["subz_C_dxy"] = raw_c
    out["raw_feat_C_dxy"] = raw_dxy

    # --- D: risk (VIX + GVZ log change) ---
    vix = panel.get("VIX")
    if vix is not None and vix.notna().any():
        lv = np.log(vix.replace(0, np.nan).clip(lower=1e-6))
        raw_vix = lv.diff(20)
        z_vix = rolling_z(raw_vix, w, zc)
    else:
        raw_vix = pd.Series(np.nan, index=panel.index)
        z_vix = pd.Series(np.nan, index=panel.index)

    gvz = panel.get("GVZ")
    if gvz is not None and gvz.notna().any():
        lg = np.log(gvz.replace(0, np.nan).clip(lower=1e-6))
        raw_gvz = lg.diff(20)
        z_gvz = rolling_z(raw_gvz, w, zc)
    else:
        raw_gvz = pd.Series(np.nan, index=panel.index)
        z_gvz = pd.Series(np.nan, index=panel.index)

    raw_d = _nanmean_row(pd.DataFrame({"vix": z_vix, "gvz": z_gvz}))
    out["subz_D_vix"] = z_vix
    out["subz_D_gvz"] = z_gvz
    out["raw_feat_D_vix"] = raw_vix
    out["raw_feat_D_gvz"] = raw_gvz

    # --- F: flow (COT level-z + ETF raw-sign) ---
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

    # Bug fix 3: negate speculative COT for contrarian direction
    # The subz columns store the DIRECTIONAL z (negated for contrarian signals)
    # so that downstream discrete_from_z produces the correct sign.
    out["subz_F_cot_mm"] = -z_mm            # contrarian level-z
    out["subz_F_cot_prod"] = z_pr             # trend-confirming level-z
    out["subz_F_cot_other"] = -z_cot_other    # contrarian level-z
    out["subz_F_imm_legacy"] = -z_imm_legacy  # contrarian level-z

    # For the category-level raw composite, use the direction-corrected z-scores
    z_cot = _nanmean_row(
        pd.DataFrame({"a": -z_mm, "b": z_pr, "o": -z_cot_other, "i": -z_imm_legacy})
    )

    gl = panel.get("gld_shares_lagged")
    if gl is not None and gl.notna().any():
        raw_etf = gl.pct_change(5, fill_method=None).replace([np.inf, -np.inf], np.nan)
        z_etf = rolling_z(raw_etf, w, zc)
    else:
        raw_etf = pd.Series(np.nan, index=panel.index)
        z_etf = pd.Series(np.nan, index=panel.index)
    raw_f = _nanmean_row(pd.DataFrame({"cot": z_cot, "etf": z_etf}))
    out["subz_F_etf"] = z_etf
    out["raw_feat_F_etf"] = raw_etf

    # --- G: GPR optional ---
    gpr = panel.get("gpr_monthly")
    if cfg.include_gpr and gpr is not None and gpr.notna().any():
        raw_gpr = gpr.diff(3)
        raw_g = rolling_z(raw_gpr, max(w, 60), zc)
        out["subz_G_gpr"] = raw_g
        out["raw_feat_G_gpr"] = raw_gpr
    else:
        raw_g = pd.Series(np.nan, index=panel.index)

    out["raw_A"] = raw_a
    out["raw_B"] = raw_b
    out["raw_C"] = raw_c
    out["raw_D"] = raw_d
    out["raw_F"] = raw_f
    out["raw_G"] = raw_g
    out["vol_scale_A"] = vol_scale

    # --- Per-category direction & confidence ---
    # v3: category direction uses discrete_from_raw on composite raw feature
    # (weighted z is already sign-aligned, so sign(composite_z) is a reasonable
    # proxy for the mean of sign(raw) votes when most legs agree).
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
        out["dir_G"] = pd.Series(np.nan, index=panel.index)
        out["conf_G"] = pd.Series(0.0, index=panel.index)

    out.loc[:, "conf_A"] = out["conf_A"] * out["vol_scale_A"].fillna(1.0)

    # --- Regime gate (200d SMA on XAUUSD) ---
    # Forward-fill to handle NaN gaps (weekends/holidays in daily panel)
    xau = panel["xauusd"].ffill()
    sma200 = xau.rolling(cfg.regime_sma_window, min_periods=cfg.regime_sma_window).mean()
    # Use prior day's data to avoid look-ahead
    out["regime_bullish"] = (xau.shift(1) >= sma200.shift(1)).astype(float)
    # Cold-start: first 200 bars have no SMA → NaN regime → no gate applied
    out["regime_bullish"] = out["regime_bullish"].where(sma200.shift(1).notna())

    return out


def attach_consensus(cat: pd.DataFrame, panel: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    """v3 consensus: weighted mean of non-abstaining category votes + regime gate."""
    cfg = cfg or settings
    letters = ["A", "B", "C", "D", "F"]
    if cfg.include_gpr:
        letters.append("G")

    # Stack directions and confidences (NaN = abstain in v3)
    dir_df = pd.DataFrame({L: cat[f"dir_{L}"] for L in letters})
    conf_df = pd.DataFrame({L: cat[f"conf_{L}"] for L in letters})

    # Count active (non-NaN) votes per row
    active_count = dir_df.notna().sum(axis=1)

    # Weighted mean of non-abstaining votes
    weighted_sum = (dir_df * conf_df).sum(axis=1, skipna=True)
    weight_total = conf_df.where(dir_df.notna()).sum(axis=1, skipna=True)
    weighted_mean = weighted_sum / weight_total.replace(0, np.nan)

    # Direction from weighted mean
    raw_dir = np.sign(weighted_mean).astype(float)
    raw_dir = raw_dir.fillna(0.0)

    # Flat if fewer than min_active_votes (Bug fix 2)
    raw_dir = raw_dir.where(active_count >= cfg.min_active_votes, 0.0)

    # Regime gate: bullish regime blocks shorts → flat
    regime = cat.get("regime_bullish")
    if regime is not None:
        bullish = regime.fillna(False).astype(bool)
        raw_dir = raw_dir.where(~(bullish & (raw_dir < 0)), 0.0)

    cat["consensus_dir_raw"] = raw_dir

    # Confidence: vote agreement — high when non-abstaining votes cluster
    # Compute as abs(weighted_mean) scaled to 0-100
    agreement = weighted_mean.abs().clip(0, 1) * 100.0
    cat["consensus_conf"] = agreement.fillna(0.0)
    cat["consensus_dir"] = raw_dir
    cat["consensus_active_votes"] = active_count

    r = panel["xauusd"].pct_change(fill_method=None)
    # Position timing: signal at COB T → hold T→T+1. shift(1) maps signal to forward return.
    lag = cat["consensus_dir"].shift(1)
    cat["strat_return"] = lag.fillna(0.0) * r.fillna(0.0)
    cat["strat_return_long_only"] = (
        cat["consensus_dir"].clip(lower=0.0).shift(1).fillna(0.0) * r.fillna(0.0)
    )

    # Per-category P&L
    for L in letters:
        lag_l = cat[f"dir_{L}"].shift(1).fillna(0.0)
        cat[f"strat_return_{L}"] = lag_l * r.fillna(0.0)
        cat[f"strat_return_{L}_long_only"] = (
            cat[f"dir_{L}"].clip(lower=0.0).shift(1).fillna(0.0) * r.fillna(0.0)
        )

    # Per raw leg: direction from raw feature sign (raw-sign) or z-score (level-z)
    thr = cfg.threshold
    for col in list(cat.columns):
        if not col.startswith("subz_"):
            continue
        sid = col[len("subz_"):]
        zs = cat[col]
        td = f"tuned_dir_{sid}"
        if td in cat.columns:
            d = cat[td]
        elif sid in RAW_SIGN_SUBSIGNALS:
            # Bug fix 1: raw-sign features use sign(raw_feature) for direction
            raw_col = f"raw_feat_{sid}"
            if raw_col in cat.columns:
                d = discrete_from_raw(cat[raw_col])
            else:
                d = discrete_from_z(zs, thr)
        else:
            # Level-z signals (COT etc.): direction from sign(z)
            # Contrarian sign already baked into subz columns (Bug fix 3)
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
