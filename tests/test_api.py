import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ["GOLD_DATA_DIR"] = str(ROOT / "data")


def test_health_and_latest_json_no_nan():
    from gold_signal.api.main import app, clear_signal_cache

    clear_signal_cache()
    with TestClient(app) as ac:
        h = ac.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert "status" in body
        j = ac.get("/api/v1/signals/latest")
        if j.status_code != 200:
            pytest.skip("local data missing for full API test")
        raw = json.dumps(j.json())
        assert "NaN" not in raw and "nan" not in raw.lower()
        data = j.json()
        assert data["consensus"]["direction"] in (-1, 0, 1)  # v3: 0 = flat (abstention / regime gate)
        wf = ac.get("/api/v1/walk-forward")
        assert wf.status_code == 200
        assert "walk_forward" in wf.json()
        wf2 = ac.get("/api/v1/backtest/walk-forward")
        assert wf2.status_code == 200
        wfj = wf.json()
        assert "subsignal_backtests" in wfj
        assert "A_mom_5d" in wfj["subsignal_backtests"]
        assert "long_only" in wfj["subsignal_backtests"]["A_mom_5d"]
        ec = wfj["equity_curve_tail"]
        assert ec and "l" in ec[0]
        assert "buy_hold_backtest" in wfj
        assert "equity_tail_rebased_sub" in wfj["buy_hold_backtest"]
        assert "full_sample_stats" in wfj
        wf0 = wfj["walk_forward"]
        assert wf0["n_steps"] >= len(wf0["steps"])
        assert len(wf0["steps"]) == wf0["steps_in_payload"]
        assert "oos_vs_buy_hold" in wfj["walk_forward"]
        latest = j.json()
        assert "signal_legs" in latest
        assert any(leg.get("id") == "A_mom_5d" for leg in latest["signal_legs"])
