"""Supabase client for fetching daily_prices time-series."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from gold_signal.config import Settings


def get_client(cfg: Settings):
    from supabase import create_client

    if not cfg.supabase_url or not cfg.supabase_service_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set to load market data."
        )
    return create_client(cfg.supabase_url, cfg.supabase_service_key)


def fetch_daily_prices(
    client,
    table: str,
    tickers: Iterable[str],
    start: str,
    page_size: int = 1000,
) -> pd.DataFrame:
    """Fetch (date, ticker, open, high, low, close, volume) rows for the given tickers.

    Paginates with .range() because Supabase caps PostgREST responses at 1000 rows.
    Returns a long DataFrame with `date` parsed as datetime.
    """
    tickers = list(tickers)
    if not tickers:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])

    all_rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            client.table(table)
            .select("date,ticker,open,high,low,close,volume")
            .in_("ticker", tickers)
            .gte("date", start)
            .order("date")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    if not all_rows:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])
    return df
