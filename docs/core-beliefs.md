# Core Beliefs

These are the operating principles for working in this repository. They apply to both human developers and AI agents. When you're unsure how to approach a decision, come back to these.

## On Specifications

**Specs are the source of truth for intent.** Before writing any code, read the relevant spec. If no spec exists for what you're building, write one first. A spec doesn't need to be perfect — it needs to exist so that intent is captured and reviewable.

**Specs are living documents.** If you discover during implementation that the spec is wrong or incomplete, update the spec first, then update the code. Never silently diverge from a spec. The gap between spec and code is where bugs hide.

**Every spec must be verifiable.** A spec that can't be checked against the code is just a wish. Write specs with concrete types, explicit API shapes, and observable behaviors so that verification is mechanical, not subjective.

## On Planning

**Plans before code.** For any work that touches more than one file or takes more than an hour, create a plan. Small changes can use a lightweight plan (a few sentences in the PR description). Complex work requires an ExecPlan in `docs/plans/active/`.

**Plans are self-contained.** A plan must contain everything needed for someone with zero context to pick it up and execute. Don't reference "what we discussed" or "the previous approach." Embed the knowledge directly.

**Plans are living documents.** Update the plan as you make progress, discover surprises, or change direction. The plan should always reflect the current state of the work, not the original vision.

## On Quality

**Verification over trust.** Don't assume code is correct because it runs. For substantive changes, use `.agents/workflows/implement-and-verify.md` and compare behavior to specs. Add automated tests (`specs/testing-strategy.md`) as the pipeline grows.

**Observable outcomes over internal attributes.** Define acceptance as behavior a human can verify: e.g. `python3 scripts/integrate_bloomberg.py` completes and `data/*.csv` refresh.

**Fix the system, not the symptom.** When something fails, ask what capability is missing and how to make it legible in specs and scripts.

## On Context

**Context is a scarce resource.** Keep `AGENTS.md` slim. Point to deeper docs. Load only what you need for the current task.

**The repository is the memory.** Write decisions in specs, plans, `TODO.md`, and `docs/quality.md`. If it's not in a file, it doesn't exist.

**Stale docs are worse than no docs.** Update docs as you go. If you can't update now, add a note: STALE — needs update after X.

## On Implementation

**Depth-first, not breadth-first.** Build one thing completely — spec, implementation, verification — before moving to the next.

**Small, verifiable steps.** Keep `python3 scripts/integrate_bloomberg.py` passing after changes when touching the data pipeline.

**Idempotent and safe.** Integration scripts should be safe to re-run; outputs go to `data/` under version control policy you choose.

## On Simplicity

**Design for removal.** Prefer small modules and clear boundaries over heavy frameworks until the product needs them.

**When everything is important, nothing is.** Be selective about what gets a spec and what lives only in `docs/architecture.md`.

**Start simple, add complexity only when forced.**
