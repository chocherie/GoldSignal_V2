import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from gold_signal.backtest.walk_forward import walk_forward_report
from gold_signal.config import Settings


def test_walk_forward_produces_steps():
    idx = pd.date_range("2000-01-01", periods=1200, freq="B")
    r = pd.Series(np.random.randn(len(idx)) * 0.001, index=idx)
    cfg = Settings()
    cfg.wf_is_days = 200
    cfg.wf_oos_days = 42
    cfg.wf_step_days = 42
    rep = walk_forward_report(r, cfg, warmup_days=400)
    assert rep["n_steps"] >= 1
    assert rep["steps"][0]["oos_sharpe"] == rep["steps"][0]["oos_sharpe"]
