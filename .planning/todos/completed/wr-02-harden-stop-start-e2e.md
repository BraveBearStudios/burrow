<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
created: 2026-06-14
title: Harden stop-start e2e — scoped selectors + backend isolation
area: ui/e2e
source: 05-REVIEW.md WR-02
severity: warning
files:
  - ui/tests/e2e/stop-start.spec.ts
---

## Problem

`stop-start.spec.ts` uses unscoped `.first()` and global text + count assertions
over a non-isolated serial backend (no DB reset, no per-test cleanup). It passes
reliably today only because per-test localStorage isolation keeps a single panel
open — an implicit, brittle invariant that a future test (or a parallelized run)
could break.

Surfaced by the Phase 5 code review (05-REVIEW.md WR-02). The suite is green
(7/7) today; this is robustness/maintainability hardening, deferred to backlog.

## Solution

Scope the selectors to the panel under test (e.g. a per-workspace test id or a
`within(panel)` locator), and add per-test cleanup (destroy created workspaces)
or a backend DB reset between tests so the assertions no longer depend on the
single-open-panel side effect.
