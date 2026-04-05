"""Golden-style check: panel loads from fixture CSVs (synthetic minimal)."""

from pathlib import Path

import numpy as np
import pandas as pd

from gold_signal.etl.panel import load_raw_panel
from gold_signal.config import Settings


def test_panel_merge_aligns_dates(tmp_path):
    idx = pd.date_range("2020-01-02", periods=5, freq="B")
    gold = pd.DataFrame(
        {"Open": 1.0, "High": 1.1, "Low": 0.9, "Close": 1.0, "Volume": 100.0}, index=idx
    )
    gold.to_csv(tmp_path / "gold_price.csv")
    xau = pd.DataFrame({"Close": 1800.0 + np.arange(len(idx))}, index=idx)
    xau.to_csv(tmp_path / "xauusd_spot.csv")
    im = pd.DataFrame(
        {
            "TNX": 2.0,
            "DXY": 100.0,
            "VIX": 20.0,
            "USGG2YR": 1.5,
            "TIPS_REAL_10Y": 0.5,
            "USGGBE10": 2.0,
        },
        index=idx,
    )
    im.to_csv(tmp_path / "intermarket.csv")
    pd.DataFrame({"gc2_price": 1.01, "gc1_open_interest": 1e5}, index=idx).to_csv(
        tmp_path / "market_structure_bbg.csv"
    )
    pd.DataFrame({"gld_shares": 1e8}, index=idx).to_csv(tmp_path / "etf_fundamentals.csv")
    pd.DataFrame({"Close": 180.0, "Volume": 1e6}, index=idx).to_csv(tmp_path / "gld_etf.csv")
    pd.DataFrame({"Close": 36.0, "Volume": 5e5}, index=idx).to_csv(tmp_path / "iau_etf.csv")
    cot_idx = pd.to_datetime(["2019-12-31"])
    pd.DataFrame({"managed_money_net": [100.0], "producer_net": [-50.0]}, index=cot_idx).to_csv(
        tmp_path / "cot_data.csv"
    )
    cfg = Settings()
    cfg.fred_api_key = ""
    panel, meta = load_raw_panel(tmp_path, cfg)
    assert len(panel) == len(idx)
    assert "xauusd" in panel.columns
    assert "cot_managed_money_net" in panel.columns
    assert panel["gold_etf_volume_total"].iloc[-1] == 1.5e6
    assert not meta["warnings"] or isinstance(meta["warnings"], list)
