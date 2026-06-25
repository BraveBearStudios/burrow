<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
created: 2026-06-15
title: Harden stop-start e2e cleanup robustness (3 Phase-7 review warnings)
area: ui/e2e
source: 07-REVIEW.md W1/W2/W3
severity: warning
resolves_phase: 10
files:
  - ui/tests/e2e/stop-start.spec.ts
  - ui/src/components/WorkspaceLayout.test.tsx
---

## Problem

Phase 7 (CICD-09) hardened `stop-start.spec.ts`, but the Phase-7 code review found three
robustness gaps in the hardening itself (0 blockers; all green today):

- **W1 — cleanup is serial-dependent, not parallel-safe.** `createdIds` is a single
  module-level array; correctness depends entirely on `mode: "serial"`. The "parallel-safe"
  comment overstates it — dropping serial mode would silently leak/mis-delete rows.
- **W2 — `afterEach` `request.delete(...)` result is discarded.** A 500 cleanup passes
  silently and leaves the row alive; the leak then surfaces in an unrelated later test.
- **W3 — the two-Start-affordance invariant is never asserted.** Neither the e2e (scopes to the
  `role=status` placeholder) nor vitest (uses `[0]`) checks `toHaveCount(2)`. A regression that
  drops the header Start button while stopped would pass every test.

Deferred from Phase 7 (green/verified 5/5) to backlog: fixing means re-running the
flaky-on-Windows e2e, best done with a clean run. Decided at the Phase-7 boundary (1:50 AM).

## Solution

- W1: track created ids per-test (local array reset in `beforeEach`) OR keep `mode: serial` and
  correct the comment to "order-independent under serial mode" (honest).
- W2: assert the cleanup DELETE succeeded — `const res = await request.delete(...); expect(res.ok()).toBeTruthy()` (or fail the test/log loudly on a non-ok cleanup).
- W3: add an explicit assertion that a stopped panel exposes exactly two `Start workspace`
  affordances (`toHaveCount(2)` in the e2e + `getAllByRole(...).toHaveLength(2)` in vitest), so a
  dropped header Start surfaces as a failure.
