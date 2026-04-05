"""Rolling z-scores, RSI/MACD, persistence, confidence."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_z(s: pd.Series, window: int, clip: float = 4.0, min_periods: int | None = None) -> pd.Series:
    mp = min_periods or max(20, window // 4)
    m = s.rolling(window, min_periods=mp).mean()
    sd = s.rolling(window, min_periods=mp).std()
    z = (s - m) / sd.replace(0, np.nan)
    return z.clip(-clip, clip)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd_histogram(close: pd.Series) -> pd.Series:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()
    return macd - sig


def discrete_deadband(z: pd.Series, tau: float) -> pd.Series:
    """
    Research / tuning: long +1 if z > tau, short -1 if z < -tau, flat 0 if |z| <= tau.
    NaN maps to 0 (no position). ``tau`` must be >= 0.
    """
    tau = float(max(0.0, tau))
    out = pd.Series(0.0, index=z.index, dtype=float)
    valid = z.notna()
    zz = z.astype(float)
    out.loc[valid & (zz > tau)] = 1.0
    out.loc[valid & (zz < -tau)] = -1.0
    return out


def discrete_from_z(z: pd.Series, threshold: float = 0.1) -> pd.Series:
    """
    Map rolling z to {-1, +1} only (always in market on that leg):
    long if z > 0, short if z < 0, z == 0 → long, NaN → long.
    (threshold kept for API compatibility; not used for direction.)
    """
    _ = threshold
    s = np.sign(z).astype(float)
    s = s.replace(0.0, 1.0)
    s = s.fillna(1.0)
    return s


def confidence_from_z(z: float | np.floating, threshold: float = 0.5) -> float:
    _ = threshold
    if z is None:
        return 0.0
    zf = float(z)
    if not np.isfinite(zf):
        return 0.0
    az = min(3.0, abs(zf))
    return float(min(100.0, 50.0 + 20.0 * az))


def confidence_series_from_z(z: pd.Series, threshold: float = 0.5) -> pd.Series:
    """Vectorized ``confidence_from_z`` (NaN / non-finite → 0)."""
    _ = threshold
    x = z.to_numpy(dtype=float, copy=False)
    out = np.zeros(len(x), dtype=float)
    m = np.isfinite(x)
    if m.any():
        az = np.minimum(3.0, np.abs(x[m]))
        out[m] = np.minimum(100.0, 50.0 + 20.0 * az)
    return pd.Series(out, index=z.index, dtype=float)


def apply_persistence(direction: pd.Series, min_same: int = 2) -> pd.Series:
    """
    Only change direction after `min_same` consecutive days at the new proposed level.
    Initial stretch adopts the first non-NaN value immediately.
    """
    out = pd.Series(np.nan, index=direction.index, dtype=float)
    eff = np.nan
    pending = np.nan
    run = 0
    for i, t in enumerate(direction.index):
        d = direction.iloc[i]
        if np.isnan(d):
            out.iloc[i] = eff if not np.isnan(eff) else 0.0
            continue
        if np.isnan(eff):
            eff = d
            pending = np.nan
            run = 0
            out.iloc[i] = eff
            continue
        if d == eff:
            pending = np.nan
            run = 0
            out.iloc[i] = eff
            continue
        if np.isnan(pending) or d != pending:
            pending = d
            run = 1
            out.iloc[i] = eff
            continue
        run += 1
        if run >= min_same:
            eff = pending
            pending = np.nan
            run = 0
        out.iloc[i] = eff
    return out.fillna(0.0)


def log_return(close: pd.Series, days: int) -> pd.Series:
    return np.log(close / close.shift(days))
