"""Load merged market panel from Supabase `daily_prices` (long → wide)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from gold_signal.config import Settings, settings
from gold_signal.etl.supabase_client import fetch_daily_prices, get_client


# ticker → {supabase_field: panel_column}
TICKER_MAP: dict[str, dict[str, str]] = {
    "GC1_Comdty": {
        "open": "gc1_open",
        "high": "gc1_high",
        "low": "gc1_low",
        "close": "gc1_close",
        "volume": "gc1_volume",
    },
    "GC2_Comdty": {"close": "gc2_price"},
    "XAUUSD_Curncy": {"close": "xauusd"},
    "USGG10YR_Index": {"close": "TNX"},
    "USGG2YR_Index": {"close": "USGG2YR"},
    "USGGBE10_Index": {"close": "USGGBE10"},
    "DXY_Index": {"close": "DXY"},
    "USDJPY_Curncy": {"close": "USDJPY"},
    "VIX_Index": {"close": "VIX"},
    "SPX_Index": {"close": "SPX"},
    "H0A0_Index": {"close": "HY_OAS"},
    "CL1_Comdty": {"close": "OIL"},
    "XBTUSD_BGN_Curncy": {"close": "BTC"},
    "TIP_US_Equity": {"close": "TIP"},
    "GVZ_Index": {"close": "GVZ"},
    "XAUL1M_Curncy": {"close": "GOLD_LEASE"},
    "GTII10_Govt": {"close": "TIPS_REAL_10Y"},
    "CFFDUORN_Index": {"close": "cot_other_reportables_net"},
    "GPRXGPRD_Index": {"close": "gpr_daily"},
    ".SHFEPREM_Index": {"close": "GOLD_CHINA_PREM"},
    ".GOLDPRM_Index": {"close": "GOLD_PREMIUM"},
    "SI1_Comdty": {"close": "SI1"},
    "CESIUSD_Index": {"close": "CESI"},
    "BCOMGC_Index": {"close": "BCOMGC"},
    "GOLDLNPM_Index": {"close": "GOLD_LN_PM"},
    "GLD_US_Equity": {"volume": "gld_etf_volume"},
    "IAU_US_Equity": {"volume": "iau_etf_volume"},
    "CFFDUMML_Index": {"close": "cot_managed_money_long"},
    "CFFDUMMS_Index": {"close": "cot_managed_money_short"},
    "CFFDUMMN_Index": {"close": "cot_managed_money_net"},
    "CFFDUPML_Index": {"close": "cot_producer_long"},
    "CFFDUPMS_Index": {"close": "cot_producer_short"},
    "CFFDUPMN_Index": {"close": "cot_producer_net"},
}


COT_COLUMNS = (
    "cot_managed_money_long",
    "cot_managed_money_short",
    "cot_managed_money_net",
    "cot_producer_long",
    "cot_producer_short",
    "cot_producer_net",
    "cot_other_reportables_net",
)


def load_raw_panel(
    data_dir: Path | str | None = None, cfg: Settings | None = None
) -> tuple[pd.DataFrame, dict]:
    """Build the wide market panel from Supabase `daily_prices`.

    `data_dir` is accepted for backwards compatibility but ignored.
    """
    cfg = cfg or settings
    meta: dict = {"source": "supabase", "warnings": []}

    client = get_client(cfg)
    long_df = fetch_daily_prices(
        client,
        cfg.supabase_table,
        list(TICKER_MAP.keys()),
        cfg.supabase_observation_start,
    )

    if long_df.empty:
        raise RuntimeError(
            f"No rows returned from Supabase table {cfg.supabase_table!r} "
            f"for the configured tickers (start={cfg.supabase_observation_start})."
        )

    idx = pd.DatetimeIndex(sorted(long_df["date"].unique()))
    panel = pd.DataFrame(index=idx)

    tickers_loaded: list[str] = []
    missing: list[str] = []

    for ticker, field_map in TICKER_MAP.items():
        sub = long_df.loc[long_df["ticker"] == ticker]
        if sub.empty:
            missing.append(ticker)
            for col in field_map.values():
                panel[col] = np.nan
            continue
        tickers_loaded.append(ticker)
        sub = sub.set_index("date").sort_index()
        # Some tickers have multiple rows per date in Supabase — keep the last.
        sub = sub[~sub.index.duplicated(keep="last")]
        for field, panel_col in field_map.items():
            if field in sub.columns:
                panel[panel_col] = pd.to_numeric(sub[field], errors="coerce").reindex(idx)
            else:
                panel[panel_col] = np.nan

    # Legacy alias used by some downstream code paths
    if "USGG2YR" in panel.columns:
        panel["TWO"] = panel["USGG2YR"]

    # gpr_daily → gpr_monthly forward-filled (categories.py expects gpr_monthly)
    if "gpr_daily" in panel.columns and panel["gpr_daily"].notna().any():
        panel["gpr_monthly"] = panel["gpr_daily"].ffill()
    else:
        panel["gpr_monthly"] = np.nan

    # ETF volume aggregate
    gld_v = panel.get("gld_etf_volume", pd.Series(np.nan, index=idx))
    iau_v = panel.get("iau_etf_volume", pd.Series(np.nan, index=idx))
    panel["gold_etf_volume_total"] = (
        pd.DataFrame({"g": gld_v, "i": iau_v}).sum(axis=1, min_count=1)
    )

    # COT release lag (data is published with a few business-day delay)
    lag = cfg.cot_release_lag_bdays
    if lag:
        for col in COT_COLUMNS:
            if col in panel.columns and panel[col].notna().any():
                shifted = panel[col].copy()
                shifted.index = shifted.index + pd.tseries.offsets.BDay(lag)
                shifted = shifted[~shifted.index.duplicated(keep="last")]
                panel[col] = shifted.reindex(idx).ffill()

    # Optional series not present in Supabase yet — keep columns NaN so signals degrade.
    for opt_col in (
        "gc1_open_interest",
        "gld_shares",
        "gld_aum",
        "iau_shares",
        "iau_aum",
        "gld_shares_lagged",
        "GOLD_INDIA_PREM",
        "GOLD_CB_HOLDINGS",
        "GOLD_CHINA_IMPORT",
        "GOLD_INDIA_IMPORT",
        "shadow_rate",
    ):
        if opt_col not in panel.columns:
            panel[opt_col] = np.nan

    panel = panel.sort_index()

    meta.update(
        {
            "tickers_loaded": tickers_loaded,
            "missing_tickers": missing,
            "rows": int(len(panel)),
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "table": cfg.supabase_table,
            "start": cfg.supabase_observation_start,
        }
    )
    if missing:
        meta["warnings"].append(
            f"Tickers missing from {cfg.supabase_table}: {', '.join(missing)}"
        )
    return panel, meta
