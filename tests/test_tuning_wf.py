import numpy as np
import pandas as pd

from gold_signal.backtest.walk_forward import _sharpe
from gold_signal.config import Settings
from gold_signal.signals.transforms import discrete_deadband
from gold_signal.tuning.deflated_sharpe import deflated_sharpe_haircut, expected_sharpe_selection_bias
from gold_signal.tuning.engine import _best_tau_on_raw, _strat_returns
from gold_signal.tuning.horizon import raw_a_with_momentum_weights
from gold_signal.tuning.wf_steps import WfStepBounds, iter_wf_step_bounds, wf_warmup_days


def test_discrete_deadband_band_and_nan():
    z = pd.Series([np.nan, -1.0, -0.05, 0.0, 0.05, 1.0], index=pd.date_range("2020-01-01", periods=6))
    d = discrete_deadband(z, 0.1)
    assert d.iloc[0] == 0.0
    assert d.iloc[1] == -1.0
    assert d.iloc[2] == 0.0
    assert d.iloc[3] == 0.0
    assert d.iloc[4] == 0.0
    assert d.iloc[5] == 1.0


def test_iter_wf_step_bounds_matches_length():
    cfg = Settings(wf_is_days=10, wf_oos_days=5, wf_step_days=5, z_window=20)
    warm = wf_warmup_days(cfg)
    n = warm + 5 * 3 + 2
    bounds = iter_wf_step_bounds(n, cfg)
    assert len(bounds) >= 1
    b0 = bounds[0]
    assert b0.is_end == b0.oos_start
    assert b0.oos_end - b0.oos_start == cfg.wf_oos_days


def test_best_tau_returns_feasible_tau():
    idx = pd.date_range("2020-01-01", periods=80)
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    z = pd.Series(rng.normal(0, 1, len(idx)), index=idx)
    b = WfStepBounds(0, is_start=10, is_end=50, oos_start=50, oos_end=70)
    taus = [0.0, 0.5, 1.0]
    tau_star, is_s, oos_s, _ = _best_tau_on_raw(z, r, b, taus)
    assert tau_star in taus
    st = _strat_returns(discrete_deadband(z, tau_star), r)
    assert is_s == _sharpe(st.iloc[b.is_start : b.is_end])
    assert oos_s == _sharpe(st.iloc[b.oos_start : b.oos_end])


def test_raw_a_momentum_weights_sums():
    idx = pd.date_range("2020-01-01", periods=5)
    cat = pd.DataFrame(
        {
            "subz_A_mom_5d": [1.0, 1.0, 1.0, 1.0, 1.0],
            "subz_A_mom_20d": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_mom_60d": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_rsi": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_macd": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_oi": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_curve": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_gc12_spread": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_lease": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_india_prem": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_china_prem": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_cb_holdings": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_china_import": [0.0, 0.0, 0.0, 0.0, 0.0],
            "subz_A_india_import": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )
    raw = raw_a_with_momentum_weights(cat, 1.0, 0.0, 0.0)
    assert (raw == 1.0 / 12.0).all()


def test_deflated_sharpe_haircut_reduces_with_many_trials():
    m = expected_sharpe_selection_bias(50, 42)
    assert m > 0
    d = deflated_sharpe_haircut(1.0, 50, 42)
    assert d < 1.0
