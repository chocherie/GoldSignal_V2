"""Weighted horizon / leg composites for research tuning (category raw z)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _nanmean_row(df: pd.DataFrame) -> pd.Series:
    return df.mean(axis=1, skipna=True)


def raw_a_with_momentum_weights(cat: pd.DataFrame, w5: float, w20: float, w60: float) -> pd.Series:
    """``raw_A`` with weighted momentum block; other A inputs unchanged (equal mean)."""
    z_mom = w5 * cat["subz_A_mom_5d"] + w20 * cat["subz_A_mom_20d"] + w60 * cat["subz_A_mom_60d"]
    return _nanmean_row(
        pd.DataFrame(
            {
                "m": z_mom,
                "r": cat["subz_A_rsi"],
                "d": cat["subz_A_macd"],
                "o": cat["subz_A_oi"],
                "c": cat["subz_A_curve"],
                "g": cat["subz_A_gc12_spread"],
                "l": cat["subz_A_lease"],
                "i": cat["subz_A_india_prem"],
                "h": cat["subz_A_china_prem"],
                "b": cat["subz_A_cb_holdings"],
                "ci": cat["subz_A_china_import"],
                "ii": cat["subz_A_india_import"],
            }
        )
    )


def raw_b_weighted(cat: pd.DataFrame, wn: float, wr: float, ws: float, wc: float) -> pd.Series:
    """Weighted sum of B sub-zs with row-wise renormalization over available legs."""
    cols = ["subz_B_nom", "subz_B_real", "subz_B_shadow", "subz_B_2s10s"]
    w = np.array([wn, wr, ws, wc], dtype=float)
    z = cat[cols].to_numpy(dtype=float)
    mask = np.isfinite(z)
    w_row = w.reshape(1, -1) * mask
    den = w_row.sum(axis=1)
    num = (z * w.reshape(1, -1) * mask).sum(axis=1)
    out = np.full(len(cat), np.nan, dtype=float)
    ok = den > 1e-12
    out[ok] = num[ok] / den[ok]
    return pd.Series(out, index=cat.index)


def z_cot_block(cat: pd.DataFrame) -> pd.Series:
    cols = [
        "subz_F_cot_mm",
        "subz_F_cot_prod",
        "subz_F_cot_other",
        "subz_F_imm_legacy",
    ]
    return cat[cols].mean(axis=1, skipna=True)


def raw_f_weighted(cat: pd.DataFrame, w_cot: float, w_etf: float) -> pd.Series:
    """Blend COT composite and ETF z; if only one side valid, use it; if neither, NaN."""
    z_c = z_cot_block(cat).to_numpy(dtype=float)
    z_e = cat["subz_F_etf"].to_numpy(dtype=float)
    mc = np.isfinite(z_c)
    me = np.isfinite(z_e)
    both = mc & me
    only_c = mc & ~me
    only_e = ~mc & me
    out = np.full(len(cat), np.nan, dtype=float)
    out[only_c] = z_c[only_c]
    out[only_e] = z_e[only_e]
    out[both] = w_cot * z_c[both] + w_etf * z_e[both]
    return pd.Series(out, index=cat.index)


# Preset weight grids (sum to 1 where multiple components apply)
A_MOM_WEIGHT_TRIPLES: list[tuple[float, float, float]] = [
    (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
    (0.5, 0.3, 0.2),
    (0.2, 0.3, 0.5),
    (0.6, 0.25, 0.15),
    (0.15, 0.25, 0.6),
    (0.7, 0.2, 0.1),
    (0.1, 0.2, 0.7),
]

B_WEIGHT_QUADS: list[tuple[float, float, float, float]] = [
    (0.25, 0.25, 0.25, 0.25),
    (0.5, 0.2, 0.2, 0.1),
    (0.2, 0.5, 0.2, 0.1),
    (0.2, 0.2, 0.5, 0.1),
    (0.1, 0.2, 0.2, 0.5),
    (0.4, 0.3, 0.2, 0.1),
]

F_COT_ETF_WEIGHTS: list[tuple[float, float]] = [(0.5, 0.5), (0.25, 0.75), (0.75, 0.25), (0.4, 0.6), (0.6, 0.4)]
