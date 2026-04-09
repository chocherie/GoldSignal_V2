"""Human-readable ids for each raw leg that feeds a category composite."""

# id -> category letter, short label (UI + API)
# v3: removed B_shadow; updated COT labels for contrarian/trend-confirming semantics.
SUBSIGNAL_META: dict[str, dict[str, str]] = {
    "A_mom_5d": {"category": "A", "label": "5d momentum (GC1 log ret)", "type": "raw-sign"},
    "A_mom_20d": {"category": "A", "label": "20d momentum", "type": "raw-sign"},
    "A_mom_60d": {"category": "A", "label": "60d momentum", "type": "raw-sign"},
    "A_rsi": {"category": "A", "label": "RSI(14) vs 50", "type": "raw-sign"},
    "A_macd": {"category": "A", "label": "MACD histogram", "type": "raw-sign"},
    "A_oi": {"category": "A", "label": "5d %\u0394 open interest", "type": "raw-sign"},
    "A_curve": {"category": "A", "label": "GC2/GC1 curve 20d \u0394 log ratio", "type": "raw-sign"},
    "A_gc12_spread": {"category": "A", "label": "GC1\u2212GC2 20d \u0394", "type": "raw-sign"},
    "A_lease": {"category": "A", "label": "Gold lease / forward 20d \u0394", "type": "raw-sign"},
    "A_india_prem": {"category": "A", "label": "India gold premium 20d \u0394", "type": "raw-sign"},
    "A_china_prem": {"category": "A", "label": "China gold premium 20d \u0394", "type": "raw-sign"},
    "A_cb_holdings": {"category": "A", "label": "Central bank gold holdings 20d \u0394", "type": "raw-sign"},
    "A_china_import": {"category": "A", "label": "China gold import 20d \u0394", "type": "raw-sign"},
    "A_india_import": {"category": "A", "label": "India gold import 20d \u0394", "type": "raw-sign"},
    "A_gsr": {"category": "A", "label": "Gold/Silver ratio 20d \u0394", "type": "raw-sign"},
    "B_nom": {"category": "B", "label": "10Y nominal \u039420d (\u2212\u0394)", "type": "raw-sign"},
    "B_real": {"category": "B", "label": "Real / breakeven \u039420d (\u2212\u0394)", "type": "raw-sign"},
    "B_2s10s": {"category": "B", "label": "2s10s spread \u039420d (\u2212\u0394)", "type": "raw-sign"},
    "B_cesi": {"category": "B", "label": "Citi US Econ Surprise (\u2212level)", "type": "raw-sign"},
    "C_dxy": {"category": "C", "label": "DXY log \u039420d (\u2212\u0394)", "type": "raw-sign"},
    "D_vix": {"category": "D", "label": "Log VIX \u039420d", "type": "raw-sign"},
    "D_gvz": {"category": "D", "label": "Log GVZ \u039420d", "type": "raw-sign"},
    "F_cot_mm": {"category": "F", "label": "COT managed-money net (contrarian level-z)", "type": "contrarian-level-z"},
    "F_cot_prod": {"category": "F", "label": "COT producer net (trend level-z)", "type": "trend-level-z"},
    "F_cot_other": {"category": "F", "label": "COT other reportables net (contrarian level-z)", "type": "contrarian-level-z"},
    "F_imm_legacy": {"category": "F", "label": "COT legacy non-commercial net (contrarian level-z)", "type": "contrarian-level-z"},
    "F_etf": {"category": "F", "label": "GLD shares 5d %\u0394", "type": "raw-sign"},
    "G_gpr": {"category": "G", "label": "GPR monthly \u03943", "type": "raw-sign"},
}
