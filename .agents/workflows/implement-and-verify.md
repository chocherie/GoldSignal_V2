# Implement and Verify

## Purpose

Execute a phase from `TODO.md` with built-in quality gates. After implementation, spawn 2 independent review subagents that compare the code against the spec. Fix any issues found, then re-review until clean. This ensures each phase is solid before moving on.

## When to Use

Use this workflow when:
- Implementing any phase from `TODO.md`
- Making significant changes to an existing system
- You want high confidence that code matches the spec

Do NOT use this workflow when:
- Making trivial changes (typo fixes, config tweaks)
- The feature has no corresponding spec

## Prerequisites

Before running this workflow, ensure:
- [ ] The relevant `specs/{system}.md` exists and is up to date
- [ ] The phase is defined in `TODO.md` with clear tasks
- [ ] The project builds and existing tests pass (clean baseline)

## Steps

### Step 1: Read the Spec and Plan

Read the spec file(s) for the system(s) you're implementing. Check `specs/README.md` for the index (e.g. `specs/tasks.md` for task-related code). Include the spec in context. Understand:
- What the system should do (Overview, API, Core Types)
- How it should handle errors (Error Handling section)
- What design decisions were made and why (Design Decisions section)

Identify the tasks in `TODO.md` for this phase. Plan the implementation order — dependencies first, then features that build on them.

### Step 2: Implement

Work through each task in the phase:
1. Implement the feature following the spec
2. Write tests as you go (unit tests at minimum)
3. Check off each task in `TODO.md` as completed
4. Ensure the project builds and tests pass after each task

**Key rule:** If you discover the spec is wrong or incomplete during implementation, update the spec first, then implement. Never silently diverge from the spec.

### Step 3: Self-Review

Before spawning review subagents, do a quick self-review:
1. Re-read the spec from top to bottom
2. For each section, verify the code matches:
   - Do the types match "Core Types"?
   - Do the endpoints match "API / Interface"?
   - Are all error codes from "Error Handling" implemented?
   - Are security considerations addressed?
3. Fix any obvious gaps

### Step 4: Spawn Review Subagents

Spawn 2 independent subagents. Each subagent receives:
- The spec file path(s)
- The code file paths that were changed
- A review checklist (see below)

**Subagent 1 — Spec Compliance Reviewer:**
```
Review the following code against the spec. For each section of the spec,
verify the code implements it correctly:

1. TYPES: Do code types match spec types? Missing fields? Wrong types?
2. API: Do endpoints match? Correct methods, paths, request/response shapes?
3. ERRORS: Are all error codes from the spec implemented? Correct HTTP status codes?
4. SECURITY: Are auth checks, validation rules, and rate limits implemented?
5. DATABASE: Does the schema match? Are indexes created?

For each issue found, report:
- Section of spec that's violated
- What the spec says
- What the code does
- Severity: CRITICAL (breaks functionality) / MAJOR (missing feature) / MINOR (style/naming)
```

**Subagent 2 — Behavioral Reviewer:**
```
Review the following code for correctness and robustness:

1. EDGE CASES: Are null/undefined/empty inputs handled?
2. ERROR PATHS: Do all try/catch blocks handle errors appropriately?
3. STATE: Are state transitions valid? Can invalid states occur?
4. CONCURRENCY: Are there race conditions? (if applicable)
5. PERFORMANCE: Any obvious N+1 queries, missing indexes, or unbounded loops?

For each issue found, report:
- File and line number (approximate)
- Description of the issue
- Suggested fix
- Severity: CRITICAL / MAJOR / MINOR
```

### Step 5: Triage Review Findings

Collect findings from both subagents. For each finding:

| Action | When |
| :--- | :--- |
| **Fix immediately** | CRITICAL or MAJOR severity |
| **Fix if quick** | MINOR severity, < 5 minutes to fix |
| **Log for later** | MINOR severity, requires significant work |
| **Dismiss** | False positive — document why in the review |

**Important:** Not every finding is a real issue. Subagents may flag things that are intentional design decisions. Check the "Design Decisions" section of the spec before fixing.

### Step 6: Fix and Re-Review

If CRITICAL or MAJOR issues were found:
1. Fix all CRITICAL and MAJOR issues
2. Run tests to ensure fixes don't break anything
3. Spawn 2 new review subagents (same prompts as Step 4)
4. Repeat until no CRITICAL or MAJOR issues found

**Maximum iterations: 3.** If issues persist after 3 rounds, stop and escalate to the user. There may be a fundamental spec problem that needs human judgment.

### Step 7: Finalize (Done Checklist)

Once reviews are clean, run the full test suite one final time. Then complete this checklist. Do not consider the phase done until all items are checked:

- [ ] `TODO.md` — all tasks checked off, phase status updated to "Complete"
- [ ] `docs/quality.md` — grades updated for affected domains
- [ ] `specs/README.md` — verification status updated
- [ ] If you followed an ExecPlan in `docs/plans/active/`: update its status; when done, move to `docs/plans/completed/`

## Review Findings Template

Use this format to track findings across review rounds:

```markdown
## Review Round {{N}}

### Subagent 1: Spec Compliance
| # | Section | Issue | Severity | Status |
|---|---------|-------|----------|--------|
| 1 | API     | ...   | MAJOR    | Fixed  |

### Subagent 2: Behavioral
| # | Location | Issue | Severity | Status |
|---|----------|-------|----------|--------|
| 1 | file.ts:42 | ... | MINOR | Logged |

### Summary
- Issues found: X
- Fixed: Y
- Logged for later: Z
- Dismissed: W
- **Result: PASS / NEEDS ANOTHER ROUND**
```

## Success Criteria

The workflow is complete when:
- [ ] All phase tasks in `TODO.md` are checked off
- [ ] Review subagents report zero CRITICAL or MAJOR issues
- [ ] All tests pass
- [ ] Done checklist (Step 7) fully completed

## Troubleshooting

### Subagents keep finding new issues each round

**Symptom:** Each review round introduces new issues instead of converging

**Solution:** The fixes are likely introducing new problems. Slow down — fix one thing at a time, run tests after each fix, and ensure you're not breaking other parts of the system.

### Subagents disagree with each other

**Symptom:** Subagent 1 says the code is correct, Subagent 2 says it's wrong

**Solution:** Check the spec. If the spec is ambiguous, update it to be explicit. The spec is the tiebreaker.

### Hitting the 3-iteration limit

**Symptom:** After 3 rounds, there are still MAJOR issues

**Solution:** Stop and escalate. This usually means the spec has a design flaw, or the implementation approach is fundamentally wrong. Re-read the spec's "Design Decisions" section and consider whether the approach needs to change.

## Notes

- The 2-subagent pattern works because different review perspectives catch different issues
- Spec Compliance catches "did we build the right thing?" — Behavioral catches "did we build it right?"
- Keep review rounds focused — don't expand scope mid-review
- Log MINOR issues rather than fixing them mid-flow to avoid yak-shaving
