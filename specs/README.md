# Specifications index — Gold Dashboard V2

| Spec | Purpose | Status | Verified |
| :--- | :--- | :--- | :--- |
| [data-pipeline.md](./data-pipeline.md) | `integrate_bloomberg.py` inputs/outputs | Implemented | Partial (smoke only, 2026-03-22) |
| [data-contract.md](./data-contract.md) | Bloomberg + FRED field mapping, staggered starts | Implemented | Partial |
| [execution-timing.md](./execution-timing.md) | Cutoff vs T+1 execution audit checklist | Implemented | N/A |
| [deploy-hosted.md](./deploy-hosted.md) | Phase 2 API + static frontend deploy | Reference | N/A |
| [bloomberg-bdh-paste-plan.md](./bloomberg-bdh-paste-plan.md) | Excel BDH paste layout + data locality | Reference | N/A |
| [testing-strategy.md](./testing-strategy.md) | pytest / future tests | Draft | No |
| [wf-tuning-research.md](./wf-tuning-research.md) | WF per-leg / category tuning (research CLI) | Implemented | Partial |

## Status legend

| Status | Meaning |
| :--- | :--- |
| Draft | Not fully implemented |
| Implemented | Code matches intent |
| Reference | Process / layout, not a single module |

## Verification legend

| Verified | Meaning |
| :--- | :--- |
| Yes (date) | Compared to code / smoke test |
| Partial | Smoke or partial review |
| No | Not yet verified |

## Creating a new spec

1. Add `specs/{feature}.md`.
2. Register it in the table above.
3. Link from `docs/architecture.md` if it is a major system.
