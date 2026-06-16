<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
created: 2026-06-14
title: Wire onTerminalEvent fast-reconcile in LeafPanel (dead Pitfall-4 path)
area: ui/workspace-layout
source: 05-REVIEW.md WR-01
severity: warning
files:
  - ui/src/components/WorkspaceLayout.tsx
  - ui/src/hooks/useWorkspaces.ts
  - ui/src/components/TerminalPanel.tsx
---

## Problem

`TerminalPanel` accepts an `onTerminalEvent` prop and `useTerminal` fires it on
terminal error/close — the documented "Pitfall 4: WS events are fresher than the
poll" fast-reconcile — and `useInvalidateWorkspaces` exists to service it. But
`WorkspaceLayout.LeafPanel` never passes `onTerminalEvent`, and
`useInvalidateWorkspaces` has zero production call sites. The fast-reconcile is
dead: the UI silently degrades to the ~3s poll on a terminal drop.

**Pre-existing from v1.0** — not introduced by Phase 5. Surfaced by the Phase 5
code review (05-REVIEW.md WR-01) because `WorkspaceLayout.tsx` was in scope.
Deferred to backlog (out of Phase 5's stop/start + drawer-polish scope).

## Solution

Wire `onTerminalEvent={invalidate}` in `LeafPanel` via `useInvalidateWorkspaces`,
and land a failing-first test asserting the workspace list invalidates on a
terminal error/close event. Low-risk, ~1-line production change plus the test.
