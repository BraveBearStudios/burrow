<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 10-persistence-data-model-reaper-carve-out
plan: 02
subsystem: testing
tags: [playwright, e2e, stop-start, test-hardening, 07r]

# Dependency graph
requires:
  - phase: 07-backlog-fixes
    provides: "CICD-09 panel-scoped locators + per-test id-scoped backend isolation (W1) in stop-start.spec.ts"
  - phase: 05-frontend-stop-start
    provides: "TerminalPanel stopped placeholder + Start CTA + header Start button (UI-07/UI-08)"
provides:
  - "07r-hardened stop/start e2e suite: W2 asserted cleanup DELETE ([200,404]) + W3 two-Start-affordance assertion"
  - "A regression guard that fails loudly if the header Start button is dropped while stopped, or if a cleanup DELETE silently fails"
affects: [phase-13-setup-wizard-ui, phase-14-real-infra-acceptance]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "e2e cleanup asserts its own success (status in [200,404]) so a swallowed teardown surfaces at root cause, not as a downstream flaky order-dependent failure"
    - "Assert affordance COUNT (toHaveCount) before a strict-mode scoped CLICK — count proves both buttons render; the scoped click stays unambiguous"

key-files:
  created: []
  modified:
    - "ui/tests/e2e/stop-start.spec.ts - W2 asserted afterEach DELETE; W3 two-affordance assertion in the round-trip test"

key-decisions:
  - "Used a distinct `stoppedRegion` const for the W3 placeholder-CTA visibility assertion rather than reusing the later `placeholder` const, keeping the existing placeholder-scoped Start CLICK byte-for-byte unchanged"

patterns-established:
  - "Self-asserting e2e teardown: capture the cleanup response and assert its status so a silent backend cleanup failure cannot leak fixture state across tests"
  - "Count-then-scoped-click: assert toHaveCount(2) over a multi-match role query, then scope the actual click to one region for strict-mode safety"

requirements-completed: [TEST-02]

# Metrics
duration: 5min
completed: 2026-06-25
---

# Phase 10 Plan 02: Stop/Start e2e Hardening (07r) Summary

**Hardened the stop/start Playwright suite — the afterEach cleanup DELETE is now asserted ([200,404]) and a stopped panel must expose BOTH Start affordances (header icon + placeholder CTA, toHaveCount(2)) — closing the last two 07r gaps with the suite staying order-independent.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-25T10:03:19Z
- **Completed:** 2026-06-25T10:09:10Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- **W2 — asserted cleanup DELETE:** the `afterEach` now captures the `request.delete` response and asserts `expect([200, 404]).toContain(res.status())`. A silently-failing backend cleanup (which would leak Fake state into a sibling test and surface as a flaky order-dependent failure) now fails the test at its root cause. Cleanup stays id-scoped over `createdIds` — no broad DB wipe introduced (T-10-02B accept holds).
- **W3 — both Start affordances asserted:** after a Stop, the round-trip test asserts `getByRole("button", { name: "Start workspace" })` has count 2 (header button `TerminalPanel.tsx:374-383` + placeholder CTA `:461-476`), then asserts the placeholder CTA is visible inside the `role="status"` "Workspace stopped" region. A regression that drops the header Start button while stopped now fails the count.
- **Order-independence (W1) verified unchanged:** the existing per-test `createdIds` tracking + unique-per-run `stamp` names + the placeholder-scoped Start CLICK were left exactly as-is; the suite ran green both whole and with the round-trip test in isolation.

## Task Commits

Each task was committed atomically:

1. **Task 1: W2 — assert the cleanup DELETE succeeds in afterEach** - `11cf299` (test)
2. **Task 2: W3 — assert both Start affordances after a stop** - `e06b771` (test)

**Plan metadata:** see the final `docs(10-02)` commit.

## Files Created/Modified
- `ui/tests/e2e/stop-start.spec.ts` - W2: capture + assert the afterEach cleanup DELETE status in `[200, 404]`. W3: after Stop, assert `toHaveCount(2)` over the two "Start workspace" buttons + the placeholder CTA visible in the `role="status"` region. Existing W1 id-tracking and the placeholder-scoped Start CLICK untouched.

## Decisions Made
- Introduced a separate `stoppedRegion` const for the W3 visibility assertion instead of moving/reusing the `placeholder` const that the later Start CLICK depends on. This keeps the existing strict-mode-safe placeholder-scoped click byte-for-byte unchanged (the plan explicitly required the existing click to stay as-is), at the cost of one additional locator declaration — a clean, minimal addition.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Biome was clean on the file after each edit; the full stop-start suite passed 5/5 on both runs (W2-only and W2+W3), and the round-trip test (carrying the W3 assertions) passed in isolation. No flaky re-runs were needed.

## Verification Evidence
- `npx playwright test stop-start` → **5 passed** (W2 run) and **5 passed** (W2+W3 run); the round-trip test alone → **1 passed**. The harness booted via the config `webServer` (stub ttyd + Fake-provider FastAPI + `vite preview` over `ui/dist`).
- `grep -n "toHaveCount(2)" ui/tests/e2e/stop-start.spec.ts` → line 142 (W3).
- `grep -n "expect(\[200, 404\])" ui/tests/e2e/stop-start.spec.ts` → line 97 (W2).
- `biome check tests/e2e/stop-start.spec.ts` → clean (no fixes applied) after each task.

## Threat Model Outcome
- **T-10-02A (DoS — swallowed cleanup DELETE):** mitigated. W2's status assertion makes a non-cleanup response fail the test, surfacing a leaked-Fake-state condition at the root cause.
- **T-10-02B (Tampering — broad DB wipe racing siblings):** accept upheld. Cleanup remains id-scoped over `createdIds`; no global wipe introduced.
- **T-10-SC (package installs):** N/A. No package installs — `@playwright/test` was already a committed `ui` dependency.
- No new security surface introduced (test-only edit). No Threat Flags.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TEST-02 / 07r is complete: the stop/start e2e suite now carries W1 (id tracking, pre-existing), W2 (asserted DELETE), and W3 (two-affordance) and stays order-independent.
- This plan touched only `ui/tests/e2e/stop-start.spec.ts` — it is independent of the Phase 10 api/persistence plans (10-01 mock-proxmoxer gate, the `003` migration + model/provider/saga plans) and creates no blockers for them.

## Self-Check: PASSED

- FOUND: `.planning/phases/10-persistence-data-model-reaper-carve-out/10-02-SUMMARY.md`
- FOUND: `ui/tests/e2e/stop-start.spec.ts`
- FOUND: commit `11cf299` (Task 1, W2)
- FOUND: commit `e06b771` (Task 2, W3)

---
*Phase: 10-persistence-data-model-reaper-carve-out*
*Completed: 2026-06-25*
