# Data pipeline — Bloomberg + GPR merge

## Overview

`scripts/integrate_bloomberg.py` reads **only paths inside this repository** (see `GOLD_DATA_DIR` / `GOLD_UPLOAD_DIR` validation) and writes merged **`data/*.csv`** plus `data/data_summary.json`.

## Inputs

| Source | Location | Parser |
|--------|----------|--------|
| Wide BDH workbook | `data/raw/Bloomberg/bbg_bdh_export*.xlsx` (newest match) or `GOLD_BDH_EXPORT` | `parse_wide_bdh_export()` — sheet `BBG_BDH_Excel_Paste_Table`, 3-col blocks, headers rows 3–4, data row 5+ |
| Legacy Book1 | `data/raw/Book1.xlsx` `Sheet2` | `parse_bloomberg_book1()` — overlays wide series |
| Intermarket book | `data/raw/bbg_intermarket.xlsx` | Optional overlay |
| COT grid | `data/raw/grid1.xlsx` | Optional; else COT from wide export |
| GPR daily / monthly | `data/raw/data_gpr_daily_recent.{dta,xls}`, `data/raw/data_gpr_export.{dta,xls}` | Stata or Excel |

## Outputs

`gold_price.csv`, `xauusd_spot.csv` (XAUUSD **PX_LAST** — execution / backtest returns spine), `silver_price.csv`, `gld_etf.csv`, `iau_etf.csv`, `intermarket.csv` (includes `TIPS_REAL_10Y`, `USGGBE10`, `USGG2YR` when present in BDH), `cot_data.csv`, `gpr_daily.csv`, `gpr_monthly.csv`, `etf_fundamentals.csv`, `market_structure_bbg.csv`, `seasonality.csv`, `geopolitical_proxy.csv`, `data_summary.json`.

## Verification

Run: `python3 scripts/integrate_bloomberg.py` from the project root (requires `requirements.txt`).

## Status

| Aspect | Status |
|--------|--------|
| Wide BDH parse | Implemented |
| GPR `.dta` | Implemented |
| Yahoo fallback | Optional (`--yahoo-fallback`) |
