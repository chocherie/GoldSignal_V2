# Bloomberg-Primary Data Plan (Gold Signal Dashboard)

This project treats **Bloomberg Terminal as the primary source** for every series that exists on Bloomberg. Public downloads are only used where Bloomberg does not publish the data (notably **GPR**).

## Acquisition order

1. **Export all Bloomberg daily / weekly history** via `BDH` / `HISTORY` / Excel API. Use **plain `=BDH(...)`** — each series occupies **two adjacent columns** (spill: date | value); one formula in the **left** column of each pair. Put **start/end** in **`A1`/`A2`** (BDH range inputs; template leaves them blank for you to fill). See **`references/BBG_BDH_Excel_Paste_Table.tsv`**. Target **2005-01-01 → latest** (longer is better for regime diversity).
2. **Export COT (weekly)** from `COT <GO>` → Gold (COMEX) → Disaggregated → Futures only → export the same net/long/short series listed below, or pull the listed **COT indices** via `BDH`.
3. **Download GPR** (not on Bloomberg) from [matteoiacoviello.com/gpr.htm](https://www.matteoiacoviello.com/gpr.htm) — file `data_gpr_daily_recent.xls` (daily) for the backtest; monthly export optional for long history.
4. **Merge** Bloomberg exports into the integration pipeline as the authoritative time series. Use **Yahoo Finance / FRED only as explicit backup** if a Bloomberg series is missing or fails QC (document any substitution).

## What stays non-Bloomberg

| Item | Source | Notes |
|------|--------|--------|
| GPR daily (`GPRD`, `GPRD_ACT`, `GPRD_THREAT`) | Iacoviello site | Weekly update cadence on upstream data; forward-fill to daily after merge. |
| Seasonality flags | Derived | Computed from the **gold** date index (no market data download). |

Everything else in the table below is **on Bloomberg** and should be sourced there first.

## Excel paste table (tabs between columns)

Copy from the block below into Excel (select all → paste). Columns: **Dimension**, **Purpose**, **Bloomberg ticker**, **Yellow key**, **Field**, **Frequency**, **Notes**.

```
Dimension	Purpose	Bloomberg ticker	Yellow key	Field	Frequency	Notes
1 Technical	Gold OHLCV (backbone)	GC1 Comdty	COM	PX_OPEN	Daily	Front-month COMEX gold; use continuous if you prefer roll rules—stay consistent.
1 Technical	Gold OHLCV	GC1 Comdty	COM	PX_HIGH	Daily	
1 Technical	Gold OHLCV	GC1 Comdty	COM	PX_LOW	Daily	
1 Technical	Gold OHLCV	GC1 Comdty	COM	PX_LAST	Daily	Primary close for signals/backtest.
1 Technical	Gold volume	GC1 Comdty	COM	PX_VOLUME	Daily	
2 Macro	10Y TIPS real yield (level)	USGGT10Y	Index	PX_LAST	Daily	Rising real yields → bearish gold in framework.
2 Macro	Fed effective / policy proxy	FDTR	Index	PX_LAST	Daily	Upper/lower bound evolution; use one consistent policy series.
2 Macro	US CPI YoY	CPI YOY	Index	PX_LAST	Monthly	Align to month-end; forward-fill to daily after merge.
2 Macro	US Core CPI YoY	CPUPAXFE	Index	PX_LAST	Monthly	Align to month-end; forward-fill to daily.
2 Macro	US payroll change	NFP TCH	Index	PX_LAST	Monthly	Align to release; forward-fill to daily.
2 Macro	Citi US economic surprise	CESIUSD	Index	PX_LAST	Daily	Positive surprise → hawkish tilt in model.
3 Sentiment	GLD price	GLD US	Equity	PX_LAST	Daily	ETF close for premium/discount vs gold.
3 Sentiment	GLD volume	GLD US	Equity	PX_VOLUME	Daily	Volume anomaly / sentiment.
3 Sentiment	IAU price (optional cross-check)	IAU US	Equity	PX_LAST	Daily	Optional if you want IAU-based ratios; GLD alone is enough for current engine.
3 Sentiment	IAU volume	IAU US	Equity	PX_VOLUME	Daily	Optional.
3 Sentiment	Gold implied vol	GVZ	Index	PX_LAST	Daily	CBOE Gold Volatility Index.
3 Sentiment	Economic surprise (shared)	CESIUSD	Index	PX_LAST	Daily	Same series as Dim 2.
4 Intermarket	US Dollar Index (DXY)	DXY	Index	PX_LAST	Daily	If `DXY Index` does not resolve, use your desk’s standard USDX ticker (ICE) and document it.
4 Intermarket	Equity vol	VIX	Index	PX_LAST	Daily	
4 Intermarket	WTI crude front	CL1	COM	PX_LAST	Daily	
4 Intermarket	USDJPY spot	USDJPY	Curncy	PX_LAST	Daily	Safe-haven / USD liquidity proxy.
4 Intermarket	Bitcoin USD spot	XBTUSD BGN	Curncy	PX_LAST	Daily	If unavailable, use your BGN crypto spot pair for BTC/USD and document.
4 Intermarket	10Y nominal yield	USGG10YR	Index	PX_LAST	Daily	Replaces Yahoo `^TNX` when BBG-primary.
4 Intermarket	13-week T-bill yield	USGG3M	Index	PX_LAST	Daily	Short-rate context; engine may use bill as fed-funds fallback context.
4 Intermarket	TIPS ETF (real-rate companion)	TIP US	Equity	PX_LAST	Daily	Optional if you want ETF-level TIPS alongside USGGT10Y.
4 Intermarket	Real yield (shared)	USGGT10Y	Index	PX_LAST	Daily	Same series as Dim 2.
4 Intermarket	Gold 2nd month settle	GC2	COM	PX_LAST	Daily	For GC1–GC2 curve / crowding in structure.
5 Flows	COT managed money long	CFFDUMML	Index	PX_LAST	Weekly	CFTC disaggregated gold; forward-fill to daily.
5 Flows	COT managed money short	CFFDUMMS	Index	PX_LAST	Weekly	
5 Flows	COT managed money net	CFFDUMMN	Index	PX_LAST	Weekly	
5 Flows	COT producer/merchant long	CFFDUPML	Index	PX_LAST	Weekly	
5 Flows	COT producer/merchant short	CFFDUPMS	Index	PX_LAST	Weekly	
5 Flows	COT producer/merchant net	CFFDUPMN	Index	PX_LAST	Weekly	
5 Flows	COT swap dealers net	CFFDUSWN	Index	PX_LAST	Weekly	
5 Flows	COT other reportables net (disagg., optional)	CFFDUORN	Index	PX_LAST	Weekly	Confirm on DES; same COMEX gold disaggregated report.
5 Flows	COT legacy non-commercial net (optional)	GCNCN	Index	PX_LAST	Weekly	Legacy COT “spec” proxy; confirm mnemonic for your terminal.
5 Flows	GLD shares outstanding	GLD US	Equity	EQY_SH_OUT	Daily	T+1 reporting lag in real life—honor in backtest timing audit.
5 Flows	GLD AUM	GLD US	Equity	FUND_TOTAL_ASSETS	Daily	
5 Flows	IAU shares outstanding	IAU US	Equity	EQY_SH_OUT	Daily	
5 Flows	IAU AUM	IAU US	Equity	FUND_TOTAL_ASSETS	Daily	
6 Seasonality	(none)	—	—	—	—	Derived from gold calendar only.
7 Geopol	GVZ (fear)	GVZ	Index	PX_LAST	Daily	Same as Dim 3.
7 Geopol	VIX (fear backup)	VIX	Index	PX_LAST	Daily	Same as Dim 4.
7 Geopol	GPR daily level	NOT ON BBG	—	—	Daily	See Iacoviello `GPRD` columns in xls.
7 Geopol	GPR daily threats	NOT ON BBG	—	—	Daily	`GPRD_THREAT` in authors’ file.
7 Geopol	GPR daily acts	NOT ON BBG	—	—	Daily	`GPRD_ACT` in authors’ file.
8 Structure	Gold–silver ratio numerator	GC1	COM	PX_LAST	Daily	Same as technical backbone.
8 Structure	Gold–silver ratio denominator	SI1	COM	PX_LAST	Daily	Front-month COMEX silver.
8 Structure	Futures open interest	GC1	COM	FUT_AGGTE_OPEN_INT	Daily	
8 Structure	Futures volume	GC1	COM	PX_VOLUME	Daily	
8 Structure	Gold 2nd month	GC2	COM	PX_LAST	Daily	For curve vs front.
8 Macro/structure	Bloomberg gold sub-index	BCOMGC	Index	PX_LAST	Daily	Trend confirmation / commodity beta context.
```

### Optional (not required by current `signal_engine_v2` dimensions)

These were pulled in some Yahoo bundles but are **not** used in the eight published dimensions; add only if you extend the model.

```
(Optional)	US large-cap equity	SPX	Index	PX_LAST	Daily	Not referenced in current dim1–8 composites.
```

## COT export shortcut

- `COT <GO>` → filter **Gold (COMEX)** → **Disaggregated** → **Futures only** → export **Managed Money / Producer-Merchant / Swap Dealer** long, short, net (or use the **CFFD**** indices** in the table above, which should match the same underlying filings).

## Quality checks before merge

- **One calendar**: decide **gold futures close vs London/NYC** and apply consistently with `references/execution-timing-audit.md` (asynchronous settlement across DXY, VIX, FX, ETFs).
- **Duplicates**: de-duplicate dates after paste; sort ascending.
- **Monthly series**: CPI / NFP / core CPI — forward-fill to daily **only after** alignment to announcement or month-end, per your data policy.
- **Weekly COT**: forward-fill to daily for signal merge; do not assume same-day availability as spot gold.

## Fallback policy (explicit)

If a Bloomberg series is unavailable:

1. Document the missing ticker in `data/data_summary.json` (or your QC log).
2. Substitute with the closest **Bloomberg** alternative (e.g. different USDX ticker) rather than jumping to Yahoo, when possible.
3. Use Yahoo/FRED **only** when no Bloomberg equivalent exists or licensing blocks export.

This keeps the **primary** designation meaningful: Bloomberg first, public APIs second, GPR always external.

## Local data only (this repository)

All **file** inputs for the integration script must live **inside the Gold Dashboard V2 project tree**. Paths from `GOLD_DATA_DIR` and `GOLD_UPLOAD_DIR` are validated at startup: anything outside the project root is rejected. Put Bloomberg exports, GPR files, and COT grids under e.g. **`data/raw/`** (default upload root). The only **non-local** source is optional **Yahoo Finance** when you explicitly enable fallback.

## `scripts/integrate_bloomberg.py` (Bloomberg-first)

1. **Step 1 — Bloomberg (wide export, recommended):** if `data/raw/Bloomberg/bbg_bdh_export*.xlsx` exists (newest file wins), parses sheet **`BBG_BDH_Excel_Paste_Table`** — 3-column BDH blocks, data from **row 5**. Populates GC1/GLD/IAU/macro/COT and intermarket columns (DXY, VIX, SPX, …). Override file with env **`GOLD_BDH_EXPORT`** (path inside the repo). **Legacy:** `data/raw/Book1.xlsx` (**Sheet2**), optional `data/raw/bbg_intermarket.xlsx` (**Sheet1**), `data/raw/grid1.xlsx` (COT) — merged on top of wide data when present.
2. **Step 2 — GPR:** reads `data/raw/data_gpr_daily_recent.dta` or `.xls`, and `data/raw/data_gpr_export.dta` or `.xls` (monthly).
3. **Step 3 — Yahoo:** runs **only** if you pass `--yahoo-fallback` or set environment variable `GOLD_YF_FALLBACK=1`. It fills any missing intermarket columns and, if needed, gold/silver/GLD/IAU from Yahoo (**remote**; keep off for a fully local pipeline).
4. **Step 4 — Write CSVs** under `data/` for the signal engine.

**Book1.xlsx Sheet2 — optional columns after your existing macro block:** append BDH pairs so Excel columns **42–49** carry **GC1** `PX_OPEN`, `PX_HIGH`, `PX_LOW`, `PX_LAST` (two columns per field: date, value), **50–51** for **SI1** `PX_LAST`, **52–59** for **GLD US** / **IAU US** `PX_LAST` and `PX_VOLUME` if you want fully Bloomberg-based ETF OHLCV without Yahoo. See `BOOK1_COL_MAP` in the script for exact (date_col, value_col) indices.

**Intermarket-only workbook:** export DXY, VIX, crude, TIP, Treasury yields, SPX, BTC, USDJPY into `data/upload/bbg_intermarket.xlsx` **Sheet1** using the same paired layout as Book1; column pairs default to `(2,3)` through `(18,19)` per `INTERMARKET_COL_MAP` in the script (adjust the map if your paste layout differs).

Environment overrides: `GOLD_DATA_DIR`, `GOLD_UPLOAD_DIR`, `GOLD_DATA_START`, `GOLD_DATA_END`, `GOLD_YF_FALLBACK`.
