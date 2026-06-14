<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 05-stop-start-controls-drawer-polish
verified: 2026-06-14T06:40:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 5: Stop/Start Controls + Drawer Polish Verification Report

**Phase Goal:** The operator can stop and start a workspace directly from the UI, with controls gated by the live state machine, and the activity drawer behaves correctly on a phone-width viewport with the design-system focus ring and custom scrollbar restored.
**Verified:** 2026-06-14T06:40:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

The 5 must-haves are the ROADMAP success criteria (the contract). The PLAN frontmatter must_haves (across plans 01-04) are plan-specific detail that map into these same 5; none reduce scope.

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|-----------------------------------|--------|----------|
| 1 | Stop is offerable only in `running`, calls WS-06, transitions to `stopped`, terminal disconnects | ✓ VERIFIED | `TerminalPanel.tsx:358` gates Stop to `status === "running"`; `WorkspaceLayout.tsx:89-95,130,132` wires `useStopWorkspace().mutate` into `onStop`/`stopPending`; `useTerminal.ts:178` guard + `[workspaceId, status]` dep (line 303) tears the socket down on running→stopped. Unit: `useTerminal.test.tsx` "tears the socket down on running→stopped"; `TerminalPanel.test.tsx` gating + pending tests green. E2E: `stop-start.spec.ts:62-82` real POST /stop + placeholder + `term-` count 0 — **7/7 passed live**. |
| 2 | Start is offerable only in `stopped`, calls WS-07, transitions to `running`, terminal reconnects | ✓ VERIFIED | `TerminalPanel.tsx:369` gates Start to `status === "stopped"`; placeholder CTA (lines 457-472) fires same `onStart`; `WorkspaceLayout.tsx:97-103,131,133` wires `useStartWorkspace`; `useTerminal.ts` re-runs on stopped→running → fresh socket (`connect()` line 286). Unit: "reconnects with a fresh socket on stopped→running". E2E: `stop-start.spec.ts:85-104` real POST /start + terminal remounts — **passed live**. |
| 3 | State machine is the authority — no illegal action offerable, no optimistic flip, backend rejection surfaces as readable error | ✓ VERIFIED | Status comes from server-truth `workspace?.status` (`WorkspaceLayout.tsx:126`); no Zustand status mirror anywhere. `TerminalPanel.tsx:358-380` shows neither control for creating/error/destroyed. Mutations carry no optimistic status write; the ~3s `useWorkspaces` poll reconciles. `onError` handlers (`WorkspaceLayout.tsx:91-93,99-101`) surface failures. E2E proves the REAL POST fires (not a client flip) via `waitForResponse`. |
| 4 | Phone-width (≤375px) drawer renders full-width; 360px panel above breakpoint | ✓ VERIFIED | `index.css:53` `--w-drawer: min(360px, 100vw)`; `index.css:282-286` `@media (max-width: 375px) { :root { --w-drawer: 100vw } }`; `ActivityDrawer.tsx:82` consumes `width: var(--w-drawer)`. Unit: `css-rules.test.ts:19-31` source-asserts both. E2E: `stop-start.spec.ts:111-129` boundingBox width == 375 at 375px viewport; lines 133-149 == 360 at 1024px — **both passed live**. |
| 5 | `--accent-line` focus ring (V3) + custom Burrow scrollbar (V4) across all four themes | ✓ VERIFIED | `index.css:295-298` `:focus-visible { outline: 2px solid var(--accent-line); outline-offset: 2px }`; `index.css:307-328` `::-webkit-scrollbar*` thumb `var(--border-mid)` + Firefox `scrollbar-width: thin` / `scrollbar-color`. Both tokens defined in all four theme blocks (lines 106/112, 128/134, 150/156, 172/178). Unit: `css-rules.test.ts:33-52`. E2E: `stop-start.spec.ts:160` ring paints `2px solid rgb(94,125,94)` + offset; line 209 custom 8px scrollbar pseudo-element — **both passed live**. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `ui/src/components/TerminalPanel.tsx` | Status-gated Stop/Start header buttons + stopped placeholder (before termStatus overlays) | ✓ VERIFIED | 592 lines; Stop/Start gated (358/369), pending+aria-busy (363-364/374-375), placeholder branches before overlays (425). Wired + imported by WorkspaceLayout. |
| `ui/src/components/WorkspaceLayout.tsx` | LeafPanel wires useStopWorkspace/useStartWorkspace into onStop/onStart + pending props | ✓ VERIFIED | 198 lines; both hooks imported (22-26), instantiated (63-64), passed to TerminalPanel (130-133). |
| `ui/src/components/ActivityDrawer.tsx` | Drawer width reads var(--w-drawer) | ✓ VERIFIED | 405 lines; `width: var(--w-drawer)` at line 82 (no inline literal). |
| `ui/src/index.css` | --w-drawer token + 375px override, :focus-visible ring, custom scrollbar | ✓ VERIFIED | Token (53), media override (282-286), focus ring (295-298), scrollbar (307-328), all tokens defined per theme. |
| `ui/src/hooks/useTerminal.ts` | Confirmed stopped gate | ✓ VERIFIED | `status !== "running"` guard (178), `[workspaceId, status]` dep (303) drives teardown/reconnect. |
| `ui/tests/msw/handlers.ts` | POST /stop and /start envelope handlers | ✓ VERIFIED | Handlers at lines 190, 217 returning `envelope(...)`. |
| `ui/tests/css-rules.test.ts` | CSS-source assertions for V2/V3/V4 | ✓ VERIFIED | 53 lines; tight regex source-asserts for all three rule families. |
| `ui/tests/e2e/stop-start.spec.ts` | Stop/start round-trip + 375px drawer + live ring/scrollbar | ✓ VERIFIED | Full round-trip, viewport width assertions, live CSS assertions; 7/7 e2e green. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `WorkspaceLayout.tsx` | `useWorkspaces.ts` | `useStopWorkspace`/`useStartWorkspace` mutation | ✓ WIRED | Imported (22-26), called (63-64), `.mutate` invoked in onStop/onStart (90/98). |
| `TerminalPanel.tsx` | `WorkspaceLayout.tsx` | `onStop`/`onStart` + `stopPending`/`startPending` props | ✓ WIRED | Props declared (32-38), consumed by gated buttons (365/376), passed by LeafPanel (130-133). |
| `ActivityDrawer.tsx` | `index.css` | `width: var(--w-drawer)` consumes the @theme token | ✓ WIRED | Drawer reads token (82); token defined (53) + media-overridden (284). |
| `index.css` | per-theme token blocks | `:focus-visible` + scrollbar read `--accent-line` / `--border-mid` | ✓ WIRED | Both tokens declared in all four theme blocks; rules reference them via var(). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `WorkspaceLayout`/`TerminalPanel` | `workspace.status` | `useWorkspaces()` → GET /api/v1/workspaces (server poll) | Yes — server-truth, drives gating + body swap | ✓ FLOWING |
| `TerminalPanel` body | `useTerminal` socket state | live WebSocket bridged to ttyd (real over Fake/stub in e2e) | Yes — e2e shows terminal mount/unmount on status flip | ✓ FLOWING |

No hardcoded-empty props or static returns feeding the rendered controls; status flows from the live list, not a Zustand mirror.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full vitest suite | `cd ui && npm test` | 15 files, 113/113 passed (8.39s) | ✓ PASS |
| Phase-5 gating/stopped unit subset (verbose) | `npx vitest run TerminalPanel.test.tsx useTerminal.test.tsx` | All gating/pending/placeholder/socket-gate/teardown/reconnect tests green | ✓ PASS |
| Production build | `cd ui && npm run build` | dist built, 444 modules, no errors | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| Playwright e2e (live browser, Fake provider + stub ttyd) | `cd ui && npm run e2e` | 7 passed (25.5s) — stop/start round-trip, 375px full-width drawer, 360px panel above breakpoint, live `--accent-line` ring (rgb(94,125,94)), custom 8px scrollbar | PASS |

Ports 8000/7681/4173 were free; harness ran clean, no Windows orphan flakiness encountered.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-07 | 05-01, 05-02, 05-04 | Operator can stop a running workspace (Stop enabled only when running, calls WS-06, terminal disconnects) | ✓ SATISFIED | Truth 1; gating + e2e stop leg green. |
| UI-08 | 05-01, 05-02, 05-04 | Operator can start a stopped workspace (Start enabled only when stopped, calls WS-07, terminal reconnects) | ✓ SATISFIED | Truth 2; gating + e2e start leg green. |
| UI-09 | 05-01, 05-03, 05-04 | Activity drawer full-width sheet at ≤375px, 360px panel above | ✓ SATISFIED | Truth 4; css-rules + e2e boundingBox both viewports. |
| UI-10 | 05-01, 05-03, 05-04 | `--accent-line` focus ring on keyboard focus | ✓ SATISFIED | Truth 5; css-rules + e2e live ring paint. |
| UI-11 | 05-01, 05-03, 05-04 | Custom Burrow scrollbar on scroll surfaces | ✓ SATISFIED | Truth 5; css-rules + e2e live scrollbar render. |

All 5 declared requirement IDs cross-reference cleanly to REQUIREMENTS.md (lines 34-38) and the traceability table (lines 92-96, all "Complete"). No orphaned requirements — REQUIREMENTS.md maps exactly UI-07..UI-11 to Phase 5 (line 103), all claimed by phase plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX/TODO/HACK in any phase-modified source file | — | Clean — completion is auditable |

The "PLACEHOLDER" text matches in `TerminalPanel.tsx` are the legitimate `Workspace stopped` resting-state UI (substantive heading + body + Start CTA, `role="status"`), not a stub. All five source files carry the two-line SPDX header (CLAUDE.md requirement).

### Human Verification Required

None for the v1.1 UI deliverable — every behavior is CI-provable over the Fake provider + stub ttyd, and all automated checks (113 unit + 7 e2e) are green live in this verification run.

One real-infra confirmation is a KNOWN, ACCEPTED deferral (does NOT block this phase):

- **Real-Proxmox stop→start of a live worker** (UI-07/UI-08 real-infra half) — CI never touches real Proxmox by design; the Fake provider proves the UI contract. Tracked as v1.0 acceptance debt **ACC-01** in 05-VALIDATION.md Manual-Only. This is the real-infra confirmation only; the v1.1 UI contract is fully verified.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are observably true in the codebase: Stop/Start are state-machine-gated (show-only-applicable, server-truth, no optimistic flip), the terminal disconnects on stop and reconnects on start (source + unit + live e2e), the drawer goes full-width at ≤375px and reverts to 360px above, and the `--accent-line` focus ring + custom scrollbar paint live across the token-defined themes. Unit suite 113/113, e2e 7/7, build clean, no debt markers.

**Noted but NOT a phase-5 gap (per verification notes + 05-REVIEW WR-01):** `LeafPanel` never wires `onTerminalEvent`, so the Pitfall-4 fast-reconcile (`useInvalidateWorkspaces`) is plumbed-but-dead — a terminal error/close degrades to the ~3s poll instead of an immediate invalidation. This is a pre-existing v1.0 plumbing seam, not introduced by Phase 5, and is not one of the 5 success criteria (the ~3s poll provides eventual correctness, which all stop/start truths rely on and which passes live). Recorded for the next reader; does not affect goal achievement.

---

_Verified: 2026-06-14T06:40:00Z_
_Verifier: Claude (gsd-verifier)_
