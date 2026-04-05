"""Load merged CSV panel + lags (COT, GLD) + ETF volumes + optional FRED backup for missing 2Y."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from gold_signal.config import Settings, settings
from gold_signal.etl.fred import fetch_fred_series


def _read_csv_index(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0, parse_dates=True, **kw)


def load_raw_panel(data_dir: Path | str, cfg: Settings | None = None) -> tuple[pd.DataFrame, dict]:
    """Load on-disk CSVs written by scripts/integrate_bloomberg.py."""
    cfg = cfg or settings
    data_dir = Path(data_dir)
    meta: dict = {"warnings": [], "files": {}}

    gold = _read_csv_index(data_dir / "gold_price.csv")
    meta["files"]["gold_price"] = str(data_dir / "gold_price.csv")

    xau_path = data_dir / "xauusd_spot.csv"
    if xau_path.is_file():
        xau = _read_csv_index(xau_path)
        if "Close" in xau.columns:
            xau_s = xau["Close"].rename("xauusd")
        else:
            xau_s = xau.iloc[:, 0].rename("xauusd")
    else:
        xau_s = gold["Close"].rename("xauusd")
        meta["warnings"].append(
            "xauusd_spot.csv missing — using GC1 Close as execution proxy (not plan-compliant; re-run integrate with XAUUSD in BDH export)."
        )

    im_path = data_dir / "intermarket.csv"
    if not im_path.is_file():
        raise FileNotFoundError(f"intermarket.csv not found under {data_dir}")
    inter = _read_csv_index(im_path)
    meta["files"]["intermarket"] = str(im_path)

    ms_path = data_dir / "market_structure_bbg.csv"
    if ms_path.is_file():
        ms = _read_csv_index(ms_path)
        meta["files"]["market_structure"] = str(ms_path)
    else:
        ms = pd.DataFrame()

    etf_path = data_dir / "etf_fundamentals.csv"
    if etf_path.is_file():
        etf = _read_csv_index(etf_path)
        meta["files"]["etf_fundamentals"] = str(etf_path)
    else:
        etf = pd.DataFrame()

    cot_path = data_dir / "cot_data.csv"
    if cot_path.is_file():
        cot = _read_csv_index(cot_path)
        meta["files"]["cot"] = str(cot_path)
    else:
        cot = pd.DataFrame()
        meta["warnings"].append("cot_data.csv missing — category F COT leg degraded.")

    gpr_path = data_dir / "gpr_monthly.csv"
    if gpr_path.is_file():
        gpr = _read_csv_index(gpr_path)
        meta["files"]["gpr_monthly"] = str(gpr_path)
    else:
        gpr = pd.DataFrame()

    idx = gold.index.union(xau_s.index).union(inter.index).sort_values().unique()
    idx = pd.DatetimeIndex(idx)

    panel = pd.DataFrame(index=idx)
    panel["gc1_close"] = gold["Close"].reindex(idx)
    panel["gc1_open"] = gold["Open"].reindex(idx) if "Open" in gold.columns else panel["gc1_close"]
    panel["gc1_high"] = gold["High"].reindex(idx) if "High" in gold.columns else panel["gc1_close"]
    panel["gc1_low"] = gold["Low"].reindex(idx) if "Low" in gold.columns else panel["gc1_close"]
    panel["gc1_volume"] = gold["Volume"].reindex(idx) if "Volume" in gold.columns else np.nan
    panel["xauusd"] = xau_s.reindex(idx)

    for c in inter.columns:
        panel[c] = inter[c].reindex(idx)

    if not ms.empty:
        panel["gc2_price"] = ms["gc2_price"].reindex(idx) if "gc2_price" in ms.columns else np.nan
        panel["gc1_open_interest"] = (
            ms["gc1_open_interest"].reindex(idx) if "gc1_open_interest" in ms.columns else np.nan
        )
    else:
        panel["gc2_price"] = np.nan
        panel["gc1_open_interest"] = np.nan

    if "gld_shares" in etf.columns:
        panel["gld_shares"] = etf["gld_shares"].reindex(idx)
    else:
        panel["gld_shares"] = np.nan
        meta["warnings"].append("gld_shares missing — F ETF leg degraded.")

    panel["gld_etf_volume"] = np.nan
    panel["iau_etf_volume"] = np.nan
    for fname, col in (("gld_etf.csv", "gld_etf_volume"), ("iau_etf.csv", "iau_etf_volume")):
        ep = data_dir / fname
        if ep.is_file():
            meta["files"][fname.replace(".csv", "")] = str(ep)
            edf = _read_csv_index(ep)
            if "Volume" in edf.columns:
                panel[col] = edf["Volume"].reindex(idx)

    vol_pair = panel[["gld_etf_volume", "iau_etf_volume"]]
    panel["gold_etf_volume_total"] = vol_pair.sum(axis=1, min_count=1)

    if not cot.empty and "managed_money_net" in cot.columns:
        lag = cfg.cot_release_lag_bdays
        cot_shifted = cot.copy()
        cot_shifted.index = cot_shifted.index + pd.tseries.offsets.BDay(lag)
        for c in cot.columns:
            panel[f"cot_{c}"] = cot_shifted[c].reindex(idx).ffill()
    else:
        for c in (
            "managed_money_net",
            "producer_net",
            "managed_money_long",
            "managed_money_short",
            "producer_long",
            "producer_short",
        ):
            panel[f"cot_{c}"] = np.nan

    if panel["gld_shares"].notna().any():
        panel["gld_shares_lagged"] = panel["gld_shares"].shift(cfg.gld_flow_lag_bdays)
    else:
        panel["gld_shares_lagged"] = np.nan

    if not gpr.empty and "gpr_monthly" in gpr.columns:
        gpr_shifted = gpr["gpr_monthly"].copy()
        gpr_shifted.index = gpr_shifted.index + pd.DateOffset(months=1)
        panel["gpr_monthly"] = gpr_shifted.reindex(idx).ffill()
    else:
        panel["gpr_monthly"] = np.nan

    panel["shadow_rate"] = np.nan

    if "USGG2YR" not in panel.columns or panel["USGG2YR"].isna().all():
        d2 = fetch_fred_series("DGS2", api_key=cfg.fred_api_key)
        if d2.empty:
            panel["USGG2YR"] = np.nan
        else:
            panel["USGG2YR"] = d2.reindex(idx).ffill()
            meta["warnings"].append("USGG2YR missing from Bloomberg — using FRED DGS2 where available.")

    meta["as_of_utc"] = datetime.now(timezone.utc).isoformat()
    return panel, meta
