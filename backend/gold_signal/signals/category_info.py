"""Static UI copy for Stage-1 categories (aligned with signal engine)."""

CATEGORY_INFO: dict[str, dict[str, str]] = {
    "A": {
        "title": "Technical",
        "subtitle": "GC1 Comdty + curve + optional physical overlays",
        "detail": (
            "v3 raw-sign: direction = sign(raw feature), z-score for confidence only. "
            "5d / 20d / 60d log returns on GC1 close; RSI(14) vs 50; MACD histogram; "
            "5d %\u0394 open interest; 20d \u0394 log(GC2/GC1); 20d \u0394 (GC1\u2212GC2); "
            "optional 20d \u0394 on GOLD_LEASE, GOLD_INDIA_PREM, GOLD_CHINA_PREM, GOLD_CB_HOLDINGS, "
            "GOLD_CHINA_IMPORT, GOLD_INDIA_IMPORT when present. "
            "Missing/stale features abstain (no default to long). "
            "Confidence scaled by inverse realized vol."
        ),
    },
    "B": {
        "title": "Rates",
        "subtitle": "Nominal, real/breakeven, 2s10s",
        "detail": (
            "v3 raw-sign: direction = sign(\u221220d\u0394 yield). Shadow leg removed. "
            "\u221220d \u0394 USGG10YR (falling yields \u2192 bullish gold), one leg TIPS real or breakeven, "
            "2s10s via USGG10Y\u2212USGG2Y (FRED DGS2 fallback). "
            "Missing features abstain."
        ),
    },
    "C": {
        "title": "US dollar",
        "subtitle": "DXY",
        "detail": (
            "v3 raw-sign: direction = sign(\u221220d\u0394 log(DXY)). "
            "Weaker USD \u2192 positive score (gold bullish). Missing \u2192 abstain."
        ),
    },
    "D": {
        "title": "Risk / stress",
        "subtitle": "VIX + GVZ",
        "detail": (
            "v3 raw-sign: direction = sign(20d\u0394 log(VIX or GVZ)). "
            "Rising fear/vol \u2192 bullish gold. Missing \u2192 abstain."
        ),
    },
    "F": {
        "title": "Flow & positioning",
        "subtitle": "COT (contrarian + trend) + GLD shares",
        "detail": (
            "CFTC COMEX gold: managed-money, other-reportables, and legacy non-commercial net "
            "as CONTRARIAN level-z (high speculative long \u2192 Short; low/net-short \u2192 Long). "
            "Producer net as TREND-CONFIRMING level-z (less short hedging \u2192 Long). "
            "+3 business-day release lag. "
            "5d %\u0394 GLD shares outstanding (raw-sign) after +1 session lag. "
            "Missing \u2192 abstain."
        ),
    },
    "G": {
        "title": "GPR (optional)",
        "subtitle": "Geopolitical risk",
        "detail": (
            "Monthly GPR from Iacoviello; +1 month conservative lag; raw-sign on changes. "
            "Off unless GOLD_INCLUDE_GPR=1."
        ),
    },
}
