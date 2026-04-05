"""Static UI copy for Stage-1 categories (aligned with signal engine)."""

CATEGORY_INFO: dict[str, dict[str, str]] = {
    "A": {
        "title": "Technical",
        "subtitle": "GC1 Comdty + curve + optional physical overlays",
        "detail": (
            "Composite z from: 5d / 20d / 60d log returns on GC1 close; RSI(14) vs 50; MACD histogram; "
            "5d %Δ open interest; 20d Δ log(GC2/GC1); 20d Δ (GC1−GC2) when GC2 is in the panel; "
            "optional 20d Δ z on GOLD_LEASE, GOLD_INDIA_PREM, GOLD_CHINA_PREM, GOLD_CB_HOLDINGS, GOLD_CHINA_IMPORT, "
            "GOLD_INDIA_IMPORT when present (BDH blocks — see specs/data-contract.md). Monthly series are forward-filled on the daily panel; "
            "20d Δ is a coarse proxy until you publish a custom monthly-diff series. Rolling z (252d), winsor ±4σ; vote is always long or short: "
            "sign(z) with z=0 or missing → long. Confidence scaled by inverse realized vol."
        ),
    },
    "B": {
        "title": "Rates",
        "subtitle": "Nominal, real/breakeven, 2s10s (shadow leg inactive)",
        "detail": (
            "20d Δ USGG10YR (bullish gold when yields fall → −z on Δ), one leg TIPS real or breakeven, "
            "Shadow sub-leg is not fed (zeros). 2s10s via USGG10Y−USGG2Y (FRED DGS2 fallback when 2Y missing). "
            "Averaged z-scores → one vote."
        ),
    },
    "C": {
        "title": "US dollar",
        "subtitle": "DXY",
        "detail": (
            "20d Δ log(DXY) z-scored; sign flipped so weaker USD → positive score (gold bullish). "
            "Same z-window as other categories; same sign(z) vote rule."
        ),
    },
    "D": {
        "title": "Risk / stress",
        "subtitle": "VIX",
        "detail": (
            "20d change in log(VIX) z-scored (higher fear → higher score for gold). "
            "HY OAS reserved for future use (off in baseline)."
        ),
    },
    "F": {
        "title": "Flow & positioning",
        "subtitle": "COT + GLD shares",
        "detail": (
            "CFTC COMEX gold: managed-money and producer net as level z-scores after +3 business-day release lag; "
            "optional other-reportables net (disaggregated) and legacy non-commercial net when present in `cot_data.csv` "
            "(weekly BDH — see IMM / extended COT in `specs/data-contract.md`). "
            "5d %Δ GLD shares outstanding after +1 session lag. Mean of COT legs + ETF z → category F."
        ),
    },
    "G": {
        "title": "GPR (optional)",
        "subtitle": "Geopolitical risk",
        "detail": (
            "Monthly GPR from Iacoviello; +1 month conservative lag; z on changes. "
            "Off unless GOLD_INCLUDE_GPR=1."
        ),
    },
}
