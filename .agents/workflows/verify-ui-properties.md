# Verify UI Properties with Bombadil

> **Gold Dashboard V2:** There is **no web UI in this repo yet**. Keep this workflow for when a dashboard is added; until then, rely on `python3 scripts/integrate_bloomberg.py` and (Phase 2) `pytest`.

## Purpose

Autonomously verify that a web UI behaves correctly by translating spec requirements into temporal logic properties and running Bombadil against the live application. Bombadil explores the UI through random interactions (clicks, typing, scrolling, navigation) and checks properties at every state transition — finding bugs on paths no one wrote tests for.

## When to Use

Use this workflow when:
- Implementing or modifying a web UI feature (new page, form, flow)
- After a phase completion that touched UI code
- Before a release — as a smoke test that covers unknown interaction paths
- After a refactor that changed UI behavior (complement to safe-refactor workflow)
- You want confidence that no user path crashes, dead-ends, or throws unhandled errors

Do NOT use this workflow when:
- The project has no web UI (CLI tools, libraries, backend-only services)
- The change is purely backend (API, database) with no UI impact
- You need to verify a specific deterministic flow (use Playwright/Cypress for that)

## Prerequisites

Before running this workflow, ensure:
- [ ] Bombadil is installed (`bombadil --version` works)
- [ ] `@antithesishq/bombadil` TypeScript types are installed (`npm install @antithesishq/bombadil`)
- [ ] The dev server is running and accessible at the target URL
- [ ] The relevant `specs/{system}.md` is up to date (properties are derived from specs)

## Concepts

**Bombadil properties** are temporal logic formulas checked against every state the UI reaches during exploration:

| Formula | Meaning | Use for |
| :--- | :--- | :--- |
| `always(() => P)` | P must be true at every state | Invariants: "page always has navigation" |
| `eventually(() => P).within(N, "seconds")` | P must become true within N seconds | Liveness: "loading spinner resolves" |
| `now(() => A).implies(eventually(() => B).within(N, "seconds"))` | If A is true now, B must become true within N seconds | Conditional: "if form submitted, success toast appears" |
| `now(() => A).implies(always(() => B))` | If A is true now, B must always be true after | Consequence: "after login, auth token exists" |

**Extractors** pull state from the live DOM while the browser is paused (no race conditions):

```typescript
const hasError = extract((state) =>
  !!state.document.querySelector(".error-banner")
);
```

The `state` object includes:
- `state.document` — The full DOM (query with `querySelector`, `querySelectorAll`)
- `state.window` — The window object
- `state.errors.uncaught_exceptions` — Array of unhandled JS errors
- `state.console` — Array of console entries (log, warn, error)

## Steps

### Step 1: Run Default Properties First

Before writing any custom properties, run Bombadil with its built-in defaults. This catches low-hanging fruit for free:

```bash
bombadil test {{DEV_URL}} --headless
```

**Built-in checks:**
- No HTTP 4xx/5xx responses
- No uncaught JavaScript exceptions
- No unhandled promise rejections
- No `console.error()` calls

**If violations are found:** Fix them before writing custom properties. These are basic health checks — if the app throws JS errors during random exploration, custom properties won't be useful yet.

**If no violations:** Proceed to Step 2.

### Step 2: Read the Spec and Identify Properties

Read `specs/{system}.md` for the system you're verifying. Look for requirements that translate into temporal logic:

| Look for in the spec | Translates to |
| :--- | :--- |
| "Must always show X" | `always(() => X)` |
| "After action A, shows feedback B within N seconds" | `now(() => A).implies(eventually(() => B).within(N, "seconds"))` |
| "Loading state resolves" | `now(() => loading).implies(eventually(() => !loading).within(N, "seconds"))` |
| "Error message displayed on failure" | `now(() => failed).implies(eventually(() => errorVisible).within(N, "seconds"))` |
| "Navigation is always available" | `always(() => hasNav)` |
| "No broken pages (404s reachable from UI)" | Default `no_http_error_codes` covers this |

**Key principle:** Don't try to translate every line of the spec. Focus on behavioral properties that describe what users should experience — invariants (things always true), liveness (things that eventually happen), and safety (things that never happen).

### Step 3: Write the Bombadil Spec

Create a spec file in `tests/ui-properties/`:

```typescript
// tests/ui-properties/{system}.bombadil.ts
import { always, eventually, now, extract } from "@antithesishq/bombadil";

// Always include defaults
export * from "@antithesishq/bombadil/defaults";

// --- Extractors: pull state from the DOM ---

const hasNavigation = extract((state) =>
  !!state.document.querySelector("nav, [role='navigation']")
);

const isLoading = extract((state) =>
  !!state.document.querySelector("[aria-busy='true'], .loading, .spinner, progress")
);

const hasMainContent = extract((state) =>
  !!state.document.querySelector("main, [role='main']")
);

// --- Properties: define what should be true ---

// Every page must have navigation
export const always_has_navigation = always(() => hasNavigation.current);

// Loading states must resolve within 5 seconds
export const loading_resolves = now(() => isLoading.current)
  .implies(eventually(() => !isLoading.current).within(5, "seconds"));

// Every page must have a main content area
export const always_has_content = always(() => hasMainContent.current);
```

**Naming convention:** Export names become property names in violation reports. Use `snake_case` and make them descriptive: `always_has_heading`, `form_submit_shows_feedback`, `loading_resolves_within_5s`.

### Step 4: Run and Interpret Results

```bash
# Run with your custom spec
bombadil test {{DEV_URL}} tests/ui-properties/{system}.bombadil.ts --headless --exit-on-violation

# Save traces for debugging
bombadil test {{DEV_URL}} tests/ui-properties/{system}.bombadil.ts --headless --output-path=./bombadil-traces/
```

**If no violations:** Properties hold across all explored paths. Move to Step 5.

**If violations are found:** Bombadil reports:
1. The property name that failed (your export name)
2. The temporal context (when the violation started, what actions preceded it)
3. A screenshot of the failing state
4. A JSONL trace of the full exploration

**Triage each violation:**

| Category | Action |
| :--- | :--- |
| **Real bug** (crash, missing content, broken flow) | Fix the code, re-run |
| **Spec issue** (the property is too strict or wrong) | Update the spec and property |
| **Environment issue** (slow dev server, network timeout) | Increase `within()` bounds or fix dev setup |

### Step 5: Commit Specs as Regression Tests

Once properties pass, commit the Bombadil spec files. They serve as living regression tests:

```
tests/ui-properties/
├── defaults.bombadil.ts          # Re-exports Bombadil defaults (always include)
├── tasks.bombadil.ts             # Task system properties
├── auth.bombadil.ts              # Auth flow properties
└── navigation.bombadil.ts        # Cross-cutting navigation properties
```

Add the Bombadil run to CI so these properties are checked on every push.

### Step 6: Update Quality Scorecard

After running Bombadil, update `docs/quality.md`:
- If Bombadil found violations that were fixed → note the improvement
- If Bombadil passes with custom properties → upgrade the domain's Tests grade
- If new properties were added → note them in the quality history

## Property Patterns

### Pattern: Form Submission Feedback

```typescript
const formSubmitted = extract((state) =>
  state.document.querySelector("form")?.getAttribute("data-submitted") === "true"
);
const successToast = extract((state) =>
  !!state.document.querySelector(".toast-success, [role='alert']")
);

export const form_shows_feedback = now(() => formSubmitted.current)
  .implies(eventually(() => successToast.current).within(3, "seconds"));
```

### Pattern: Auth-Gated Content

```typescript
const isLoggedOut = extract((state) =>
  !!state.document.querySelector("[data-testid='login-button']")
);
const protectedContent = extract((state) =>
  !!state.document.querySelector("[data-protected]")
);

export const no_protected_content_when_logged_out =
  always(() => !(isLoggedOut.current && protectedContent.current));
```

### Pattern: Error Recovery

```typescript
const hasError = extract((state) =>
  !!state.document.querySelector(".error-boundary, [role='alert'][data-error]")
);
const hasRetry = extract((state) =>
  !!state.document.querySelector("button[data-retry], .retry-button")
);

export const errors_offer_recovery =
  always(() => !hasError.current || hasRetry.current);
```

### Pattern: No Dead-End Pages

```typescript
const hasInteractiveElement = extract((state) => {
  const doc = state.document;
  return !!(
    doc.querySelector("a[href]") ||
    doc.querySelector("button") ||
    doc.querySelector("[role='navigation']")
  );
});

export const no_dead_ends = always(() => hasInteractiveElement.current);
```

## Success Criteria

The workflow is complete when:
- [ ] Default Bombadil properties pass with no violations
- [ ] Custom properties derived from specs pass
- [ ] Violations triaged — real bugs fixed, spec issues updated
- [ ] Bombadil spec files committed to `tests/ui-properties/`
- [ ] CI pipeline includes Bombadil run
- [ ] `docs/quality.md` updated

## Troubleshooting

### Bombadil can't find any actions

**Symptom:** "no fallback action available" error

**Solution:** The page has no interactive elements (links, buttons, inputs) that Bombadil can discover. This might mean the page renders blank, requires auth, or is a static page. Check that the URL is correct and the page has interactive content. For auth-gated apps, start Bombadil on the login page.

### Properties fail on timing

**Symptom:** `eventually` properties time out but the behavior works manually

**Solution:** Increase the `within()` bound. Dev servers are slower than production. Use generous bounds (5-10 seconds) for dev, tighter bounds for production CI.

### Too many violations from default properties

**Symptom:** `no_console_errors` triggers on benign warnings, third-party library noise

**Solution:** Write a custom spec that re-exports only the defaults you care about, or override specific defaults. Don't disable defaults permanently — fix the underlying issues when possible.

### Bombadil explores outside the intended scope

**Symptom:** Bombadil clicks links that navigate away from the app (external links, OAuth redirects)

**Solution:** Bombadil restricts exploration to the origin of the starting URL by default. If it still navigates away, this indicates your app has same-origin links that lead to unexpected places — that's a finding worth investigating.

## Notes

- Bombadil is complementary to fast-check, not a replacement. fast-check tests data properties of functions. Bombadil tests behavioral properties of UIs.
- Default properties alone (zero custom specs) catch a surprising number of real bugs. Start there.
- Properties derived from specs create a closed loop: spec → property → automated verification. This is the highest-value integration.
- Bombadil traces are JSONL files with screenshots — useful for debugging but large. Gitignore the `bombadil-traces/` directory.
- Bombadil pauses the browser at each state for consistent snapshots. This eliminates flaky test issues caused by race conditions between test code and app code.
