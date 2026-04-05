import numpy as np
import pandas as pd

from gold_signal.backtest.walk_forward import (
    cagr_pct_from_equity_multiple,
    downsample_equity_points,
    full_sample_return_stats,
)


def test_downsample_keeps_endpoints_and_cap():
    items = [{"d": str(i), "e": float(i)} for i in range(1000)]
    out = downsample_equity_points(items, 10)
    assert len(out) <= 10
    assert out[0]["d"] == "0"
    assert out[-1]["d"] == "999"


def test_cagr_flat_multiple():
    assert abs(cagr_pct_from_equity_multiple(1.0, 500)) < 1e-9


def test_volatility_annualized_is_percent_points():
    rng = np.random.default_rng(42)
    r = pd.Series(rng.normal(0.0, 0.01, 600))
    out = full_sample_return_stats(r)
    assert out["volatility_annualized"] is not None
    assert 14.0 < out["volatility_annualized"] < 18.0


def test_cagr_matches_compounded_daily_rate():
    n = 252
    daily = 0.0005
    r = pd.Series(np.full(n, daily))
    mult = float((1.0 + r).prod())
    cagr = cagr_pct_from_equity_multiple(mult, n)
    expected = ((1.0 + daily) ** 252 - 1.0) * 100.0
    assert abs(cagr - expected) < 1e-6

