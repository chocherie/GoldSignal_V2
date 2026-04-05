# Quality scorecard

**Last Updated:** 2026-03-26

## How to read this

| Grade | Meaning |
|-------|---------|
| **A** | Production-ready: spec, code, tests, reviewed |
| **B** | Functional with minor gaps |
| **C** | Work in progress |
| **D** | Scaffolded / minimal tests |
| **F** | Not started or broken |

## Domain scores

| Domain | Spec | Code | Tests | Review | Overall | Notes |
|--------|------|------|-------|--------|---------|-------|
| Data pipeline | B | B | B | Partial | B | `integrate_bloomberg.py` + ETL/fixture tests |
| Bloomberg BDH docs | B | N/A | N/A | N/A | B | Paste plan + skill alignment |
| Dashboard / UI | B | B | C | Partial | B | React dashboard; snapshot tests |
| Signals engine | B | B | B | Partial | B | FastAPI + `gold_signal`; combiner/confidence paths vectorized (2026-03-26) |

## Architectural layers

| Layer | Grade | Notes |
|-------|-------|-------|
| Error handling | C | Clear prints; could centralize logging |
| Security | N/A | Local data only; no auth surface yet |
| Observability | C | Console + `data_summary.json` |
| CI | F | No GitHub Actions / pytest in CI yet |
| Documentation | B | Scaffold + specs; keep updated |

## Known gaps

| Gap | Severity | Tracking |
|-----|----------|----------|
| Per-subleg columns in `attach_consensus` trigger pandas fragmentation warnings | Low | batch with `pd.concat` if hot path |
| CI not on GitHub Actions | Low | `TODO.md` Phase 2 optional |

## Score history

| Date | Domain | Change |
|------|--------|--------|
| 2026-03-22 | Scaffold | Initial grades after data pipeline build |
| 2026-03-26 | Signals | Vectorized `majority_combiner` + `confidence_series_from_z`; scorecard aligned with Phase 3 |
