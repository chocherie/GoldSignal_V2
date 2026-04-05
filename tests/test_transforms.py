import numpy as np
import pandas as pd

from gold_signal.signals.transforms import (
    apply_persistence,
    confidence_from_z,
    confidence_series_from_z,
    discrete_from_z,
    rolling_z,
)


def test_rolling_z_finite():
    s = pd.Series(np.random.randn(300).cumsum() + 100, index=pd.date_range("2020-01-01", periods=300))
    z = rolling_z(s, 60, clip=4.0)
    assert z.dropna().between(-4.01, 4.01).all()


def test_discrete_sign_no_neutral():
    z = pd.Series([0, 0.15, -0.2, 0.05, -0.05], index=pd.date_range("2020-01-01", periods=5))
    d = discrete_from_z(z, 0.1)
    assert list(d.values) == [1.0, 1.0, -1.0, 1.0, -1.0]

    zn = pd.Series([np.nan, 0.2], index=pd.date_range("2020-01-01", periods=2))
    assert list(discrete_from_z(zn, 0.1).values) == [1.0, 1.0]


def test_confidence_series_matches_scalar():
    idx = pd.date_range("2020-01-01", periods=5)
    z = pd.Series([np.nan, 0.0, 1.5, -4.0, 10.0], index=idx)
    got = confidence_series_from_z(z, 0.5)
    for i, t in enumerate(idx):
        assert got.loc[t] == confidence_from_z(float(z.loc[t]) if z.loc[t] == z.loc[t] else np.nan, 0.5)


def test_persistence_requires_two_days():
    d = pd.Series([1, 1, -1, -1, 1, 1], index=pd.date_range("2020-01-01", periods=6))
    out = apply_persistence(d, min_same=2)
    assert out.iloc[0] == 1
    assert out.iloc[2] == 1
    assert out.iloc[3] == -1
    assert out.iloc[4] == -1
    assert out.iloc[5] == 1
