# Walk-forward signal tuning (research-only)

## What runs

`scripts/wf_tune_signals.py` loads the merged panel, builds category z-scores (`compute_category_raw_scores`), then for each walk-forward step (same calendar as `walk_forward_report`):

1. **In-sample (IS)** slice: choose parameters that maximize **in-sample Sharpe** (√252·mean/σ on daily strategy returns).
2. **Out-of-sample (OOS)** slice: apply those parameters **unchanged** and record OOS Sharpe.

**Never** optimize on OOS — that would be look-ahead.

## Per sub-leg

For each id in `SUBSIGNAL_META`, grid over deadband **τ** (`GOLD_TUNE_TAU_N` points on [0, 1]). Direction: `discrete_deadband` (+1 / −1 / 0) with **NaN → flat**. Strategy return = lagged direction × XAUUSD daily return (same T+1 convention as production).

## Per category composite

- **A**: Grid over momentum **weights** (5d / 20d / 60d) from preset triples; composite `raw_A` uses weighted momentum block + equal mean of RSI/MACD/OI/curve. **τ = 0** on `raw_A` for weight choice, then grid **τ** on the chosen `raw_A`.
- **B**: Preset weight quadruples on the four B sub-zs; then **τ** grid.
- **F**: Preset `(w_cot, w_etf)` on COT composite vs ETF; then **τ** grid.
- **C, D**: Fixed `raw_C` / `raw_D` from the score table; **τ** grid only.
- **G**: Only if `GOLD_INCLUDE_GPR=1`; **τ** grid on `raw_G`.

## Deflated / haircut Sharpe

Grid search implies **multiple testing**. The tuner reports a conservative **haircut**: subtract `expected_sharpe_selection_bias(n_trials, n_obs)` from pooled mean OOS Sharpe (see `gold_signal.tuning.deflated_sharpe`). This is a heuristic, not a formal probabilistic Sharpe ratio or DSR.

## How to run (paths matter)

- Use your **real** project folder (e.g. where `backend/` and `scripts/` live). A placeholder like `/path/to/Gold Dashboard V2` will fail.
- **Option A:** `cd` into that folder, then `python3 scripts/wf_tune_signals.py`.
- **Option B:** From anywhere, call Python with the **absolute path** to `scripts/wf_tune_signals.py` so the shell does not look under your home directory for `scripts/`.

The script sets the process working directory to the repo root and adds `backend/` to `sys.path`; you do not need `PYTHONPATH=backend` unless you prefer it.

### Before / after metrics vs production

After a run, generate a markdown table: **CAGR %, ann. vol %, Sharpe, max DD %** on **concatenated OOS** windows only (same WF `step_idx`s as in the CSV), for each sub-leg, each category solo, and the main consensus strategy.

```bash
python3 scripts/tuning_before_after.py
```

Writes `before_after_metrics.md` and **`before_after_metrics.tsv`** (tab-separated, paste into Excel or open in Excel) next to that run’s CSVs (uses the **latest** folder under `data/tuning_runs/`). On macOS the script runs `open` on the `.tsv` once.

## Environment

| Variable | Meaning |
|----------|---------|
| `GOLD_DATA_DIR` | Data directory (default repo `data/`). |
| `GOLD_TUNE_TAU_N` | Number of τ grid points on [0, 1] (default 11). |
| `GOLD_WF_MAX_STEPS` | Cap WF steps for faster runs (optional). |
| `GOLD_INCLUDE_GPR` | Include G in tuning when set. |

Outputs: `data/tuning_runs/<timestamp>/per_leg_per_step.csv`, `per_category_per_step.csv`, `summary.json`.

Production `build_signal_table` is **unchanged** until a later integration step.
