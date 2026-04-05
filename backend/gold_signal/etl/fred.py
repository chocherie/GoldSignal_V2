"""FRED observations for optional Treasury backups (e.g. DGS2 when USGG2YR missing)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from gold_signal.config import settings


def fetch_fred_series(
    series_id: str,
    api_key: str | None = None,
    observation_start: str = "2000-01-01",
) -> pd.Series:
    """
    Return a daily Series indexed by date (UTC midnight).
    Empty series if no API key or request fails (caller sets warnings).
    """
    key = (api_key or settings.fred_api_key or "").strip()
    if not key:
        return pd.Series(dtype=float)
    params = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": observation_start,
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return pd.Series(dtype=float)
    obs = payload.get("observations") or []
    dates = []
    vals = []
    for row in obs:
        v = row.get("value")
        if v in (None, ".", ""):
            continue
        try:
            vals.append(float(v))
            dates.append(pd.Timestamp(row["date"]))
        except (TypeError, ValueError, KeyError):
            continue
    if not dates:
        return pd.Series(dtype=float)
    s = pd.Series(vals, index=pd.DatetimeIndex(dates), name=series_id)
    return s[~s.index.duplicated(keep="last")].sort_index()
