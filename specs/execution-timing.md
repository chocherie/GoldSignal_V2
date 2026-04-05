# Execution timing and no–look-ahead rules

This document is the **project audit checklist** for signal cutoffs vs trade entry. It mirrors the trading-signal-dashboard / four-eye execution-timing audit.

## Anchors (locked for v1)

| Concept | Definition |
|--------|------------|
| **Signal calendar date** | US business day `T`. |
| **Signal cutoff** | **5:00 PM Eastern** — all inputs must be **observable at or before** this time on `T` (COB aligned with **XAUUSD Curncy** mark convention from Bloomberg `DES`). |
| **Feature history** | Indicators on `T` use only data with timestamp **≤ cutoff(T)**. |
| **Execution (baseline backtest)** | Signal fixed at **COB T**; **entry** XAUUSD mid at **COB T**, **exit** at **COB T+1** (one session). Realized return on row **T+1** is `position(T) × (close_{T+1}/close_T - 1)` (implemented as `direction.shift(1) * pct_change`). |
| **Signal price (features)** | **GC1 Comdty** (and **GC2** for curve) — **signals only**; timestamps are futures-oriented and documented separately from spot COB. |
| **P&amp;L / returns** | **XAUUSD** only in the baseline backtest (not GC1), unless a labeled robustness lane is run. |

## Input last-fix reference (typical US session)

Use Bloomberg `DES` / vendor stamps to confirm; approximate ordering for a **US-centric COB**:

| Input | Typical fix (ET) | Notes |
|-------|------------------|--------|
| US cash equities, GLD | ~4:00 PM | ETF close. |
| VIX | ~4:15 PM | Cash close. |
| Many FX / spot marks (XAUUSD) | ~5:00 PM | **Project COB anchor.** |
| US Treasury yields (GG curves) | Afternoon | Generally available by 5 PM ET for daily studies. |
| CFTC COT (weekly) | Report **as-of** Tuesday; **public release** later (often Friday) | Signals use values only **after publication** — see ETL lag. |
| GPR (academic) | Monthly / weekly | Merge on **release** date + explicit lag. |

## Audit checklist (run before trusting backtest or live)

1. **Cutoff ≥ latest allowed input** — The stated cutoff is **not earlier** than the latest-settling series you allow into that day’s signal.
2. **Mark consistency** — Baseline P&amp;L uses **XAUUSD** COB **T → T+1** with the signal fixed at **T** (see table above). Confirm this matches your live execution policy (some desks use **T+1** entry only — then shift returns one bar vs this code).
3. **Weekly / monthly series** — Forward-fill only **after** applying **publication lag**; store **as-of** vs **available** dates where possible.
4. **ETF shares (GLD)** — Apply **≥1 session** reporting lag vs spot COB for flow features.
5. **COT** — Lag **report date** by **business days** to approximate public availability (default **+3** in code; confirm against current CFTC schedule).
6. **FRED Treasury (e.g. `DGS2` backup)** — Daily levels can **revise**; v1 uses latest vintage — document for production vintage use if you rely on FRED for 2Y.
7. **JSON / API** — No `NaN` in payloads; missing inputs = `null` with explicit `data_warnings`.

## One-session hold (plain language)

After cutoff on **T**, the engine emits a position (long / short / flat). The backtest attributes **one** XAUUSD session of P&amp;L: **entry at COB T**, **exit at COB T+1**. A new signal on **T+1** flips the position for the **next** session — there is **no** multi-day minimum hold in code (legacy `hold_sessions` config was removed).
