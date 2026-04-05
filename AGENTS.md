# Gold Dashboard V2

Multi-dimensional gold / macro **data integration** (Bloomberg-primary + GPR) with in-repo CSV outputs, a **FastAPI** signal engine (`backend/gold_signal/`), and a **React** dashboard (`frontend/`). All local data paths must stay inside this repository.

## Non-negotiable rules

1. **Read the spec before coding** — See `specs/README.md`; data work → `specs/data-pipeline.md`. Cursor rule: `read-spec-before-coding.mdc`.
2. **Update docs after changes** — `TODO.md`, `docs/quality.md`, affected specs. Rule: `update-docs-after-changes.mdc`.
3. **Write artifacts to disk** — Plans, reports, and decisions go under `docs/` and `specs/`. Rule: `artifacts-to-disk.mdc`.
4. **Data stays in-repo** — `GOLD_DATA_DIR` / `GOLD_UPLOAD_DIR` cannot point outside the project; see `scripts/integrate_bloomberg.py`.

## Repository map

| Document | Purpose |
| :--- | :--- |
| `TODO.md` | Phases and next tasks |
| `docs/architecture.md` | System map, tech stack, directories |
| `docs/core-beliefs.md` | Agent / dev principles |
| `docs/quality.md` | Living grades |
| `docs/plans/active/` | ExecPlans (e.g. [phase-2-pytest-ci.md](./docs/plans/active/phase-2-pytest-ci.md)) |
| `docs/plans/completed/` | Finished plans |
| `docs/reports/` | Audits and analyses |
| `specs/README.md` | Spec index |
| `specs/data-pipeline.md` | Merge script contract |
| `specs/bloomberg-bdh-paste-plan.md` | Excel BDH layout |
| `specs/testing-strategy.md` | How we test |
| `references/bloomberg-data-guide.md` | Bloomberg acquisition checklist |

## Workflows

| Workflow | When |
| :--- | :--- |
| `.agents/workflows/implement-and-verify.md` | After substantive feature work |
| `.agents/workflows/safe-refactor.md` | Refactors needing equivalence checks |
| `.agents/workflows/verify-ui-properties.md` | When a web UI exists (not yet) |

## Cursor rules (auto-injected)

| Rule | Purpose |
| :--- | :--- |
| `update-docs-after-changes.mdc` | Doc updates after implementation |
| `read-spec-before-coding.mdc` | Spec-first edits to `scripts/`, `specs/` |
| `artifacts-to-disk.mdc` | Persist plans/specs/reports |
| `bloomberg-bdh-excel.mdc` | Bloomberg BDH paste conventions |

## Commands

| Command | Purpose |
| :--- | :--- |
| `python3 -m pip install -r requirements.txt` | Install Python dependencies |
| `python3 scripts/integrate_bloomberg.py` | Merge Bloomberg + GPR → `data/*.csv` |
| `python3 scripts/integrate_bloomberg.py --yahoo-fallback` | Optional Yahoo fill (remote) |
| `./scripts/start_api.sh` | API with correct `PYTHONPATH` — run **from repo root** (`cd` into the folder that contains `backend/`; from `~` the path does not exist). If you see **Address already in use**, stop the old process: `kill $(lsof -t -iTCP:8000 -sTCP:LISTEN)` or use `GOLD_API_PORT=8001` + matching `VITE_API_PORT` in `frontend/.env` |
| `PYTHONPATH=backend python3 -m uvicorn gold_signal.api.main:app --reload --host 127.0.0.1 --port 8000` | API (manual, from repo root) |
| `PYTHONPATH=backend python3 -m pytest tests/ -q` | Tests |
| `cd frontend && npm run dev` | Dashboard dev server at **http://127.0.0.1:5173** (proxies `/health` + `/api` to `VITE_API_PORT`, default 8000) |

## Environment variables

| Variable | Purpose |
| :--- | :--- |
| `GOLD_DATA_DIR` | Output data directory (default `data/`, must be under project) |
| `GOLD_UPLOAD_DIR` | Input root (default `data/raw/`) |
| `GOLD_BDH_EXPORT` | Explicit path to wide BDH xlsx (optional) |
| `GOLD_YF_FALLBACK` | Set to `1` to allow Yahoo fallback without CLI flag |
| `FRED_API_KEY` | Optional; FRED `DGS2` when `USGG2YR` missing from intermarket |
| `GOLD_CORS_ORIGINS` | Comma-separated allowed origins for FastAPI CORS |
| `GOLD_WF_IS` / `GOLD_WF_OOS` / `GOLD_WF_STEP` | Walk-forward lengths (defaults 378 / 42 / 42) |
| `GOLD_INCLUDE_GPR` | Set `1` to include GPR in Stage-2 vote |

## How to work here

1. Read `TODO.md` for the current phase.
2. Read the relevant spec from `specs/README.md`.
3. Implement; run `python3 scripts/integrate_bloomberg.py` when touching the pipeline.
4. Update `TODO.md`, `docs/quality.md`, and spec verification status when done.

## Learned User Preferences

- For Bloomberg Terminal–linked Excel, lay out `=BDH()` so each series has its own horizontal space: the function spills **two columns** (date and value); stacking many `BDH` formulas down one column causes **#SPILL!** / overwrites.
- Use **plain `=BDH(...)`** and native spill unless the user explicitly asks for Excel 365 helpers like `CHOOSECOLS`.
- When the user asks for a Bloomberg paste table, provide a **tab-delimited copy block** in the reply when practical, not only a file path.
- For large multi-step plans, prefer **one primary executor** at a time (e.g. Cursor Composer “Building” **or** this chat) on the same files to avoid conflicting parallel edits.
- If a Composer/plan run shows **Building** with no progress for a long time, treat it as likely stuck: cancel, then continue in smaller chunks or in chat.

## Learned Workspace Facts

- GPR is **not** on Bloomberg; project inputs use **`data/raw/`** (e.g. `data_gpr_daily_recent.dta` / `data_gpr_export.dta` or legacy `.xls`) alongside **`data/raw/Bloomberg/bbg_bdh_export*.xlsx`** (see `specs/data-pipeline.md` and `references/bloomberg-data-guide.md`).
- BDH paste layout, 3-column block variant, and saved export naming are documented in **`specs/bloomberg-bdh-paste-plan.md`**, **`references/BBG_BDH_Excel_Paste_Table.tsv`**, and **`.cursor/rules/bloomberg-bdh-excel.mdc`**; the user skill **`bloomberg-excel-bdh`** under **`~/.cursor/skills/`** mirrors the Excel conventions.
- In-repo execution checklist for **pytest + CI** is **`docs/plans/active/phase-2-pytest-ci.md`**. A separate Cursor plan under **`~/.cursor/plans/`** (e.g. full webapp scope) is **not** automatically what agents follow unless it is imported or reflected under **`docs/plans/active/`**.
