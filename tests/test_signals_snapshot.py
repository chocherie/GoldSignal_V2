"""Fixed synthetic panel: signal columns exist and last row is JSON-safe."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from gold_signal.config import Settings
from gold_signal.etl.panel import load_raw_panel
from gold_signal.jsonutil import sanitize
from gold_signal.signals.categories import build_signal_table


def test_signal_table_last_row_keys(tmp_path):
    rng = np.random.default_rng(42)
    n = 400
    idx = pd.date_range("2018-01-02", periods=n, freq="B")
    g = 1200 + np.cumsum(rng.normal(0, 8, n))
    gold = pd.DataFrame(
        {
            "Open": g,
            "High": g * 1.01,
            "Low": g * 0.99,
            "Close": g,
            "Volume": rng.integers(1e4, 1e5, n),
        },
        index=idx,
    )
    gold.to_csv(tmp_path / "gold_price.csv")
    pd.DataFrame({"Close": g * 1.5 + 100}, index=idx).to_csv(tmp_path / "xauusd_spot.csv")
    im = pd.DataFrame(
        {
            "TNX": 2.5 + rng.normal(0, 0.05, n).cumsum() * 0.01,
            "DXY": 100 + rng.normal(0, 0.2, n).cumsum(),
            "VIX": 18 + np.abs(rng.normal(0, 1, n)),
            "USGG2YR": 1.2 + rng.normal(0, 0.02, n).cumsum() * 0.01,
            "TIPS_REAL_10Y": 0.3 + rng.normal(0, 0.02, n).cumsum() * 0.01,
            "USGGBE10": 2.0 + rng.normal(0, 0.02, n).cumsum() * 0.01,
        },
        index=idx,
    )
    im.to_csv(tmp_path / "intermarket.csv")
    pd.DataFrame({"gc2_price": g * 1.002, "gc1_open_interest": 1e5 + rng.normal(0, 500, n)}, index=idx).to_csv(
        tmp_path / "market_structure_bbg.csv"
    )
    pd.DataFrame({"gld_shares": 2e8 + np.cumsum(rng.normal(0, 5e4, n))}, index=idx).to_csv(
        tmp_path / "etf_fundamentals.csv"
    )
    cot_idx = pd.to_datetime(["2017-06-01", "2017-06-08"])
    pd.DataFrame({"managed_money_net": [10.0, 20.0], "producer_net": [-5.0, -8.0]}, index=cot_idx).to_csv(
        tmp_path / "cot_data.csv"
    )

    cfg = Settings()
    cfg.fred_api_key = ""
    panel, _ = load_raw_panel(tmp_path, cfg)
    sig = build_signal_table(panel, cfg)
    last = sig.iloc[-1]
    payload = {
        "consensus_dir": float(last["consensus_dir"]),
        "raw_A": float(last["raw_A"]) if last["raw_A"] == last["raw_A"] else None,
    }
    json.dumps(sanitize(payload))
    assert "consensus_dir" in sig.columns
    assert "strat_return" in sig.columns
    assert "strat_return_A" in sig.columns
    assert "strat_return_F" in sig.columns
    assert "subz_A_mom_5d" in sig.columns
    assert "strat_sub_A_mom_5d" in sig.columns
    assert "strat_return_long_only" in sig.columns
    assert "strat_return_A_long_only" in sig.columns
