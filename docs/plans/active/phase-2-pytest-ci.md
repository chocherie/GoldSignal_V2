# Phase 2 — pytest coverage + CI (ExecPlan)

This is a **living document**. Update **Progress**, **Surprises & Discoveries**, **Decision Log**, and **Outcomes** as work proceeds.

## Purpose / Big Picture

Anyone cloning **Gold Dashboard V2** can run **`pytest`** locally and see **CI pass on every push/PR**, proving that date coercion and wide BDH parsing behave as specified—without relying on the full multi-megabyte Bloomberg export or manual smoke runs. Failures surface in GitHub before bad changes merge.

## Current State

- **`scripts/integrate_bloomberg.py`** implements `_coerce_excel_date`, `_read_wide_block_series`, `parse_wide_bdh_export`, GPR readers, and `main()`. On import it resolves **`DATA_DIR`** / **`UPLOAD_DIR`** under the project root.
- **No `tests/` directory** and no **`pytest`** configuration.
- **No CI workflow** under `.github/workflows/`.
- **`specs/testing-strategy.md`** describes pytest as planned but not implemented.
- **`TODO.md`** Phase 2 lists tests + optional CI; this plan makes that concrete.

## Plan of Work

1. **Dependencies** — Add **`requirements-dev.txt`** listing `pytest` (pin a recent 8.x). Document in **`AGENTS.md`** / **`specs/data-pipeline.md`** that devs install dev deps for tests.
2. **Extract or expose testable units** — Keep production code in `scripts/integrate_bloomberg.py`. Either:
   - **Option A (preferred):** Add **`tests/conftest.py`** that puts `PROJECT_ROOT` on `sys.path` and sets env vars so import of `integrate_bloomberg` resolves paths inside the temp clone, **or**
   - **Option B:** Move pure helpers (`_coerce_excel_date`, `_must_be_under_project` logic) into **`scripts/bbg_parse_utils.py`** and import from both the script and tests (larger refactor).
   **Default in this plan: Option A** to minimize churn; if import side effects block clean tests, switch to Option B and note in Decision Log.
3. **Unit tests** — Create **`tests/test_bbg_dates.py`**: table-driven cases for `_coerce_excel_date` (datetime, Excel serial `36529` → 2000-01-04, None, bad values).
4. **Integration-style test for wide layout** — Create **`tests/test_wide_bdh_fixture.py`**: build a **minimal** openpyxl workbook in **`tmp_path`**: sheet `BBG_BDH_Excel_Paste_Table`, row 3–4 headers, row 5+ a few rows of (date, value) for one GC1 `PX_LAST` block at columns A–B, optional second block. Call **`_read_wide_block_series`** (import from module) or run a **small public helper** if you add `read_wide_sheet_blocks(ws)` for testability. Assert series length, index monotonicity, and last value.
5. **Path guard test** — One test that **`_must_be_under_project`** rejects a path outside `PROJECT_ROOT` (construct with `/tmp` or `..` traversal as appropriate on the runner OS; skip if not portable—then test only the “accept in-repo path” case).
6. **Pytest config** — Add **`pyproject.toml`** `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["."]` if needed so `import scripts.integrate_bloomberg` works, or run tests with `PYTHONPATH=.` documented in the plan’s Concrete Steps.
7. **CI** — Add **`.github/workflows/ci.yml`**: trigger on `push` and `pull_request` to default branch; job **test** on `ubuntu-latest`, Python **3.11** (and optionally **3.12** as a matrix if desired). Steps: checkout, setup-python, `pip install -r requirements.txt -r requirements-dev.txt`, `pytest -q`. Cache pip optional.
8. **Docs** — Update **`docs/quality.md`** (Tests row), **`specs/README.md`** verification, **`TODO.md`** Phase 2 checkboxes, and this plan’s **Progress**.

## Milestones

### Milestone 1: Local pytest passes

**Description:** `pytest` runs green from the repo root using only small synthetic data (no `data/raw/Bloomberg` required).

**Outcome:** `tests/` exists with at least **date coercion** + **wide block read** coverage; `requirements-dev.txt` + config present.

**Verify:**

```bash
cd "Gold Dashboard V2"
python3 -m pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Expected: all tests passed (or skipped with explicit reason).

### Milestone 2: GitHub Actions CI green

**Description:** Pushing the workflow file causes Actions to run `pytest` on Ubuntu.

**Outcome:** `.github/workflows/ci.yml` exists; PRs show a **green check** for the test job.

**Verify:** Open a PR or push to a branch; confirm workflow run succeeds. Local `act` optional—not required.

## Concrete Steps

Run from the repository root **`Gold Dashboard V2/`**.

1. Create `requirements-dev.txt`:

   ```text
   pytest>=8.0
   ```

2. Add test files as in Plan of Work (adjust names if you consolidate).

3. First successful local run:

   ```bash
   python3 -m pip install -r requirements.txt -r requirements-dev.txt
   PYTHONPATH=. pytest -q
   ```

   If imports fail, set **`pythonpath`** in `pyproject.toml` or document `PYTHONPATH=.` in **`AGENTS.md`**.

4. Add `.github/workflows/ci.yml` with Python 3.11 and the same install + `pytest -q` (working directory: repo root; set `env: PYTHONPATH: .` if needed).

5. Commit, push, confirm CI.

**Expected transcript (local):**

```text
....                                                                     [100%]
N passed in 0.XXs
```

## Validation and Acceptance

| # | Behavior |
|---|----------|
| 1 | Fresh clone + `pip install -r requirements.txt -r requirements-dev.txt` + `pytest -q` exits **0**. |
| 2 | Tests do **not** require `data/raw/Bloomberg/bbg_bdh_export*.xlsx` to exist. |
| 3 | GitHub Actions **test** job passes on default PR/push. |
| 4 | `docs/quality.md` reflects improved **Tests** grade for Data pipeline (target **B** once pytest is in place). |

## Idempotence and Recovery

- Re-running `pytest` is safe; no writes to `data/` from tests unless explicitly testing `main()` (avoid that in Phase 2—keep tests hermetic).
- CI failures: fix tests or code; re-run workflow. No database or external API in Phase 2 tests.

## Interfaces and Dependencies

| Piece | Notes |
| :--- | :--- |
| `pytest` | Dev dependency only |
| `openpyxl` | Already in `requirements.txt`; tests build tiny workbooks |
| `pandas` | Already required; used by parsers under test |

Functions to cover in tests (minimum):

- `_coerce_excel_date(val) -> pd.Timestamp | None`
- `_read_wide_block_series(ws, date_col, val_col, data_start_row=5) -> pd.Series | None`
- `_must_be_under_project(path) -> Path` (happy + sad path as feasible)

---

## Progress

- [ ] Add `requirements-dev.txt` with `pytest`
- [ ] Add `pyproject.toml` pytest section (or `pytest.ini`) + document `PYTHONPATH`
- [ ] Implement `tests/test_bbg_dates.py`
- [ ] Implement `tests/test_wide_bdh_fixture.py` (tmp_path workbook)
- [ ] Add path containment test (`_must_be_under_project`)
- [ ] Local: `pytest -q` passes
- [ ] Add `.github/workflows/ci.yml`
- [ ] CI run green on remote
- [ ] Update `docs/quality.md`, `specs/README.md`, `TODO.md`, `specs/testing-strategy.md`

## Surprises & Discoveries

(None yet.)

## Decision Log

| Date | Decision | Rationale |
| :--- | :--- | :--- |
| 2026-03-22 | ExecPlan created | User requested concrete Phase 2 plan for pytest + CI |
| | | |

## Outcomes & Retrospective

(To fill when Phase 2 is complete: what worked, what to improve, whether matrix 3.11+3.12 was worth it.)

## Revision Notes

| Date | Change |
| :--- | :--- |
| 2026-03-22 | Initial version |
