# Gold Dashboard V2 — implementation plan

**Current phase:** Phase 3  
**Last updated:** 2026-03-26

---

## Quick status

| Phase | Status | Focus |
| :--- | :--- | :--- |
| Phase 1: Data pipeline | **Complete** | Wide BDH + GPR `.dta` → `data/*.csv` + `xauusd_spot.csv` |
| Phase 2: Tests + hardening | **Complete** | pytest: transforms, combiner, ETL fixture, API smoke, walk-forward smoke |
| Phase 3: Signals + dashboard | **Complete** | `backend/gold_signal` FastAPI + `frontend` Vite React |
| Phase 4: Hosted deploy | Optional | `Dockerfile`, `specs/deploy-hosted.md` |

---

## Phase 1 — Data pipeline — COMPLETE

- [x] `parse_wide_bdh_export()` for `data/raw/Bloomberg/bbg_bdh_export*.xlsx`
- [x] GPR from `.dta` under `data/raw/`
- [x] Project-local path enforcement for `GOLD_DATA_DIR` / `GOLD_UPLOAD_DIR`
- [x] `requirements.txt`, `specs/data-pipeline.md`, `AGENTS.md`
- [x] Smoke run: `python3 scripts/integrate_bloomberg.py` succeeds

### Phase 1 verification

- [x] Integration completes without Yahoo fallback
- [x] `data/data_summary.json` written

---

## Phase 2 — Tests + hardening — COMPLETE (core)

**ExecPlan:** [`docs/plans/active/phase-2-pytest-ci.md`](./docs/plans/active/phase-2-pytest-ci.md) — CI workflow still optional.

- [x] `tests/` — transforms, combiner, ETL fixture, API smoke, walk-forward, signal snapshot
- [ ] Add `.github/workflows/ci.yml` (Ubuntu, Python 3.11, `pytest -q`) — optional
- [ ] Document failure modes in `specs/data-pipeline.md` — optional expansion

### Phase 2 verification

- [x] `pytest` passes locally
- [ ] CI green on push/PR
- [ ] Update `docs/quality.md` (Data pipeline → Tests: B or higher)

---

## Phase 3 — Signals + dashboard — COMPLETE

- [x] Signal engine + contract via `specs/data-contract.md`, `specs/execution-timing.md`, `backend/gold_signal/`
- [x] Read `data/*.csv` + FRED; FastAPI `/api/v1/*`
- [x] React + Vite in `frontend/`

### Phase 3 verification

- [x] End-to-end: raw → CSV → API → UI
- [x] Update `specs/README.md` and `docs/architecture.md`

---

## Blocked / on hold

| Item | Blocker |
| :--- | :--- |
| — | — |

---

## Decision log

| Date | Decision | Rationale |
| :--- | :--- | :--- |
| 2026-03-22 | Scaffold aligned with project-scaffold skill | Long-horizon agent execution |
| 2026-03-26 | Vectorized Stage-2 combiner + category confidence | NumPy row ops replace per-day Python in `majority_combiner`; `confidence_series_from_z` replaces `.map` in `compute_category_raw_scores` (same outputs) |
| 2026-03-30 | Vite `server.host: 127.0.0.1` | Fixes “connection failed” when opening **http://127.0.0.1:5173** while Node listened on `[::1]` only |
| 2026-03-30 | Git init + `origin` | Local `main` with 2 commits; push after creating **GoldSignal_V2** on GitHub — see `docs/reports/github-push-GoldSignal_V2.md` |
