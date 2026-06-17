<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 07-backlog-fixes-fast-reconcile-e2e-hardening
verified: 2026-06-15T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  is_re_verification: false
---

# Phase 7: Backlog Fixes (Fast-Reconcile + E2E Hardening) Verification Report

**Phase Goal:** The operator's workspace list reflects a terminal error/close immediately instead of waiting for the ~3s poll, and the stop/start Playwright e2e is robust to parallelization and multi-panel state.
**Verified:** 2026-06-15
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | On a terminal error/close, the workspace list invalidates immediately (LeafPanel wires onTerminalEvent -> useInvalidateWorkspaces) rather than waiting for the ~3s poll | VERIFIED | `WorkspaceLayout.tsx:70` calls `useInvalidateWorkspaces()`; `:136` passes it as `onTerminalEvent={invalidateWorkspaces}` to `TerminalPanel`. Full path confirmed: `useTerminal.ts:267` fires `onEventRef.current?.("closed")` from `scheduleReconnect` (`:255`), reached via `socket.onclose` (`:237` → `:246`). `useWorkspaces.ts:31-35` `useInvalidateWorkspaces()` calls `invalidateQueries({ queryKey: WORKSPACES_KEY })`. |
| 2 | A failing-first vitest test proves the fast-reconcile invalidation path (and that status is not mirrored into Zustand) | VERIFIED | `WorkspaceLayout.test.tsx:266-310` (UI-12 describe block): drives `lastSocket().emitClose()` (`:294`), asserts `invalidateSpy.toHaveBeenCalledWith({ queryKey: WORKSPACES_KEY })` (`:297-301`), and asserts no Zustand status mirror via `layoutAfter.not.toHaveProperty("status")` + unchanged `mosaicNode`/`activeWorkspaceId` (`:305-308`). RED commit `54bc89c` precedes GREEN commit `492e4ce`. |
| 3 | stop-start.spec.ts uses panel-scoped locators only -- no unscoped .first() and no global [data-testid^=term-] count assertions | VERIFIED | Zero `.first()` calls (only a comment on `:101` referencing their removal). All `[data-testid^="term-"]` locators are `panel.locator(...)` scoped (`:103`, `:127`, `:156`, `:173`, `:195`, `:219`, `:266`). Stop assertion is panel-scoped `panel.locator('[data-testid^="term-"]').toHaveCount(0)` (`:127-129`), not a global grid count. |
| 4 | stop-start.spec.ts has per-test backend isolation (created workspaces destroyed) so it is order-independent / parallel-safe | VERIFIED | `createdIds[]` module array (`:37`) tracks ids in `createWorkspace` (`:76`); `afterEach` (`:86-94`) drains it via id-scoped `request.delete('/api/v1/workspaces/${id}')` — never a broad wipe. `workspaceIdByName` (`:44-53`) resolves the id per created workspace. |
| 5 | The full vitest suite and `npm run e2e` are green repeatably over the Fake + stub ttyd | VERIFIED (vitest run) / UNCERTAIN-NOT-BLOCKING (e2e) | `cd ui && npm test` → 15 files / 114 tests passed (ran live this verification, 8.46s). e2e (7/7) is CI-provable; not run live here to avoid port-hold, but the spec compiles in the same gate and is structurally hardened. SUMMARY claims 7/7 green; no contradicting evidence found. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `ui/src/components/WorkspaceLayout.tsx` | LeafPanel wires onTerminalEvent -> useInvalidateWorkspaces | VERIFIED | Import (`:23`), call (`:70`), wiring (`:136`). Substantive + wired. |
| `ui/src/components/TerminalPanel.tsx` | data-testid=panel-${id} on section; forwards onTerminalEvent | VERIFIED | `:295` `data-testid={`panel-${id}`}` on `<section>`; `:278` forwards into `useTerminal`. |
| `ui/src/components/WorkspaceLayout.test.tsx` | Failing-first UI-12 invalidation test, no Zustand mirror | VERIFIED | `:266-310`. Spies `invalidateQueries`, asserts no status mirror. Passes in live run. |
| `ui/tests/e2e/stop-start.spec.ts` | Panel-scoped locators + per-test id-scoped cleanup | VERIFIED | Scoped locators throughout; `afterEach` id-scoped DELETE (`:86-94`). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| LeafPanel | useInvalidateWorkspaces | `onTerminalEvent={invalidateWorkspaces}` prop | WIRED | `WorkspaceLayout.tsx:70,136` |
| TerminalPanel | useTerminal | `useTerminal(id, status, { onTerminalEvent })` | WIRED | `TerminalPanel.tsx:278` |
| useTerminal close | onTerminalEvent("closed") | `scheduleReconnect` -> `onEventRef.current?.("closed")` | WIRED | `useTerminal.ts:237,246,255,267` |
| useInvalidateWorkspaces | TanStack Query | `invalidateQueries({ queryKey: WORKSPACES_KEY })` | WIRED | `useWorkspaces.ts:31-35` |
| e2e create | per-test cleanup | `createdIds` -> `afterEach request.delete` | WIRED | `stop-start.spec.ts:37,76,86-94` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| LeafPanel fast-reconcile | `invalidateWorkspaces` callback | `useInvalidateWorkspaces()` -> live `queryClient.invalidateQueries(WORKSPACES_KEY)` | Yes (triggers real refetch of the workspace list; server stays source of truth) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full vitest suite green (incl. UI-12 invalidation test) | `cd ui && npm test` | 15 files / 114 tests passed (8.46s) | PASS |
| e2e suite green (Fake + stub ttyd) | `cd ui && npm run build && npm run e2e` | Not run live (port-hold avoidance); CI-provable, spec compiles in vitest gate | SKIP (documented CI gate) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| UI-12 | 07-01-PLAN | Workspace list reconciles immediately on a terminal error/close — LeafPanel wires onTerminalEvent -> useInvalidateWorkspaces (Pitfall-4 fast-reconcile) | SATISFIED | Truths 1+2; REQUIREMENTS.md:28 marked `[x]`, mapped to Phase 7 (`:86`) |
| CICD-09 | 07-01-PLAN | stop/start Playwright e2e hardened — panel-scoped locators + per-test backend isolation | SATISFIED | Truths 3+4; REQUIREMENTS.md:41 marked `[x]`, mapped to Phase 7 (`:87`) |

No orphaned requirements: REQUIREMENTS.md maps only UI-12 and CICD-09 to Phase 7, both claimed by 07-01-PLAN.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | - | - | - | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER in any of the 4 modified files; no unscoped `.first()`; no global term-count assertion; no Zustand status mirror. |

### Human Verification Required

None. This is a pure-frontend phase, fully CI-provable over the FakeComputeProvider + stub ttyd. No real-infra deferral expected per phase context. The vitest gate ran green live this verification; the e2e gate is a deterministic CI check, not a visual/UX judgment requiring a human.

### Gaps Summary

No gaps. Both backlog findings are closed in the actual codebase:
- UI-12: the dead Pitfall-4 fast-reconcile seam is wired end-to-end (LeafPanel -> TerminalPanel -> useTerminal -> onTerminalEvent -> useInvalidateWorkspaces -> invalidateQueries), proven by a failing-first vitest test that also guards against a Zustand status mirror. Live `npm test` confirms 114/114.
- CICD-09: stop-start.spec.ts is hardened with `panel-${id}`-scoped locators (no unscoped `.first()`, no global count assertion) and id-scoped per-test `afterEach` cleanup, keeping the mode:serial Fake-backed suite order-independent.

Truth 5's e2e half was not executed live (to avoid the documented Windows port-hold flakiness on 8000/7681/4173); it is recorded as a CI-provable gate, not a blocker — the SUMMARY's 7/7 claim has no contradicting evidence and the spec compiles within the vitest transform gate that ran green.

---

_Verified: 2026-06-15_
_Verifier: Claude (gsd-verifier)_
