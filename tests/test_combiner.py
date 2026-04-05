import pandas as pd

from gold_signal.signals.combiner import majority_combiner


def test_majority_long():
    idx = pd.date_range("2020-01-01", periods=2)
    d1 = pd.Series([1, 1], index=idx)
    d2 = pd.Series([1, -1], index=idx)
    d3 = pd.Series([0, 0], index=idx)
    c1 = pd.Series([60.0, 60.0], index=idx)
    c2 = pd.Series([50.0, 50.0], index=idx)
    c3 = pd.Series([40.0, 40.0], index=idx)
    out = majority_combiner([d1, d2, d3], [c1, c2, c3], ["A", "B", "C"])
    assert out["direction"].iloc[0] == 1
    assert out["confidence"].iloc[0] > 0


def test_long_wins_when_more_longs_than_shorts_even_if_many_neutral():
    """Regression: old rule required pos > neutral, which zeroed the strategy too often."""
    idx = pd.date_range("2020-01-01", periods=1)
    dirs = [
        pd.Series([1], index=idx),
        pd.Series([1], index=idx),
        pd.Series([-1], index=idx),
        pd.Series([0], index=idx),
        pd.Series([0], index=idx),
    ]
    confs = [pd.Series([50.0], index=idx) for _ in dirs]
    out = majority_combiner(dirs, confs, list("ABCDE"))
    assert out["direction"].iloc[0] == 1
