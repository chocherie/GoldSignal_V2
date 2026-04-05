# Data contract — Bloomberg, FRED fallbacks, staggered starts

## Bloomberg wide BDH (primary)

Saved under `data/raw/Bloomberg/bbg_bdh_export*.xlsx`. Parser supports:

- **3-column blocks** (preferred): `specs/bloomberg-bdh-paste-plan.md`
- **Compact 2-column blocks**: Security row 1, Field row 2, spill from row 4 (columns D–E, F–G, …)

### Core series → internal keys / CSV columns

| Category | Bloomberg (representative) | Field | Output |
|----------|----------------------------|-------|--------|
| Gold futures (signals) | GC1 Comdty | PX_LAST, OPEN, HIGH, LOW, VOLUME, OPEN_INT | `gold_price.csv`, `market_structure_bbg.csv` |
| Gold curve | GC2 Comdty | PX_LAST | `gc2_price` in `market_structure_bbg.csv` |
| Execution / returns | XAUUSD Curncy | PX_LAST | `data/xauusd_spot.csv` |
| Nominal 10Y | USGG10YR Index | PX_LAST | `intermarket.csv` → `TNX` |
| Nominal 2Y | USGG2YR Index | PX_LAST | `intermarket.csv` → `USGG2YR` |
| 10Y breakeven | USGGBE10 Index | PX_LAST | `intermarket.csv` → `USGGBE10` |
| 10Y TIPS real | GTII10 Govt | PX_LAST | `intermarket.csv` → `TIPS_REAL_10Y` |
| USD | DXY Curncy | PX_LAST | `DXY` |
| JPY | USDJPY Curncy | PX_LAST | `USDJPY` |
| Risk | VIX Index | PX_LAST | `VIX` |
| Equity | SPX Index | PX_LAST | `SPX` |
| HY OAS | H0A0 Index | PX_LAST | `HY_OAS` (optional category D) |
| Silver | SI1 Comdty | PX_LAST | `silver_price.csv` |
| Oil | CL1 Comdty | PX_LAST | `OIL` |
| GLD | GLD US Equity | PX_LAST, EQY_SH_OUT, … | `gld_etf.csv`, `etf_fundamentals.csv` |
| IAU | IAU US Equity | PX_LAST, PX_VOLUME, … | `iau_etf.csv` |
| COT (disaggregated) | CFFDUMMN / CFFDUPMN Index (etc.) | PX_LAST | `cot_data.csv` |

**ETF volume on the panel:** `load_raw_panel` adds `gld_etf_volume` and `iau_etf_volume` from those files’ `Volume` columns, and **`gold_etf_volume_total`** = row-wise sum (each side may be missing; `min_count=1` so one fund alone still yields a total). Category **F** still uses **GLD shares outstanding** (`gld_shares`) for the ETF z-leg, not volume — use `gold_etf_volume_total` in extensions or research if you want a combined activity signal.

**Canonical COT nets (plan default):** managed money net, producer net (plus long/short legs in export for audit).

**IMM / extended COMEX gold positioning (optional, weekly):** Gold futures are **COMEX**; **IMM** is another CME division, but “IMM-style” is still used loosely for **CFTC positioning**. Add optional `cot_data.csv` columns (same **weekly** `BDH` as other COT, forward-fill + **+3 business-day** release lag):

| Role | Bloomberg (verify `DES`) | Field | `cot_data.csv` column |
|------|--------------------------|-------|------------------------|
| Disaggregated other reportables net | `CFFDUORN Index` | PX_LAST | `other_reportables_net` |
| Legacy non-commercial net | `GCNCN Index` | PX_LAST | `legacy_noncomm_net` |

Category **F** averages level z-scores across managed money, producer, and whichever of these optional nets are present. **Traders in Financial Futures (TFF)** leveraged-fund / asset-manager nets use different index mnemonics — add your own `(Security, Field)` → internal name in `WIDE_COT_SERIES` after confirming on **COT `<GO>`** / **FDM**.

### Optional category A overlays (physical / regional)

Add **three-column BDH blocks** for any subset; integrate maps Bloomberg series into `intermarket.csv`. **Default Bloomberg symbols below are placeholders** — confirm or replace on `DES` for your license (premiums are often desk-specific or computed in Excel and pasted as a custom `Index`).

| Role | Default Bloomberg (example) | Field | `intermarket.csv` column |
|------|----------------------------|-------|---------------------------|
| Gold lease / forward | `GOLDLNPM Index` | PX_LAST | `GOLD_LEASE` |
| India premium | `GOLDIPREM Index` | PX_LAST | `GOLD_INDIA_PREM` |
| China premium | `GOLDCHPREM Index` | PX_LAST | `GOLD_CHINA_PREM` |
| Central bank holdings | `GOLDCBH Index` | PX_LAST | `GOLD_CB_HOLDINGS` |
| China gold imports | `CHGLDIMP Index` | PX_LAST | `GOLD_CHINA_IMPORT` |
| India gold imports | `INGLDIMP Index` | PX_LAST | `GOLD_INDIA_IMPORT` |

Signals: **20d first-difference**, then rolling z (same window as other legs). **GC1−GC2** uses `GC1` and `GC2` **PX_LAST** already in the export (`gold_price` + `gc2_price`); no extra BDH column required.

**Imports / CB holdings** are often **monthly**; after merge they are forward-filled on the daily index, so **20d Δ** is only a rough intraday feature — prefer publishing a **custom daily or monthly-diff series** as a Bloomberg `Index` if you need cleaner timing.

To use different tickers, change the mapping in `scripts/integrate_bloomberg.py` (`WIDE_BBG_SERIES` keys).

### Staggered history (do not zero-fill pre-start)

| Series | Typical start (indicative) |
|--------|---------------------------|
| XAUUSD / GC1 daily | ~2000 in sample exports |
| GLD ETF | ~2004 listing |
| Disaggregated COT | ~2006 |
| GVZ, some macro | later |
| GPR daily | 1985+ in Iacoviello files |

The pipeline writes `data/data_summary.json` with per-file date ranges. The signal engine must tolerate **NaN** until all required legs exist.

## FRED (API key: `FRED_API_KEY`)

Used when running the FastAPI ETL merge (or tests with mocks).

| Role | FRED ID (default) | Notes |
|------|-------------------|--------|
| 2Y Treasury (2s10s backup) | `DGS2` | Merged only if `USGG2YR` missing from panel. |
| 10Y Treasury (backup) | `DGS10` | Optional cross-check; primary remains `TNX` from BBG. |

**Start dates:** Treasury series have FRED publication histories — align on **calendar** and **ffill** macro only where appropriate (see ETL).

## Public fallbacks (when Bloomberg is absent)

| Need | Source |
|------|--------|
| Gold futures | CME / Yahoo `GC=F` (rolls) — `scripts/integrate_bloomberg.py --yahoo-fallback` only |
| COT | [CFTC disaggregated COMEX gold](https://www.cftc.gov/dea/futures/deacmxsf.htm) |
| GPR | [matteoiacoviello.com/gpr.htm](https://www.matteoiacoviello.com/gpr.htm) |

## Versioning

- **as_of:** merge timestamp in API `/health` and panel meta.
- **Raw exports:** dated filenames under `data/raw/Bloomberg/`.
