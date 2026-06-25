<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0013: Persistence model (Tier-1 opt-in persistent workspaces)

## Status

Accepted

## Context

v1 workspaces are ephemeral by design: a worker is a cloned LXC that is gone when
destroyed. WSX-02 asks for **persistent** workspaces: a workspace an operator can
stop and later restart, with its disk and identity intact, rather than recreate
from scratch. The question is how much machinery that requires.

The key observation (verified against the live state machine and provider) is that
stop/start ALREADY preserves everything persistence needs:

- `stopWorkspace`/`startWorkspace` only flip `status` between `running` and
  `stopped`; they never soft-delete the row and never free the VMID. The LXC is
  stopped with `pct stop`, not destroyed, so its rootfs disk survives on the node.
- A `stopped` workspace keeps a live DB row (`deletedAt IS NULL`), so its VMID stays
  in `live_vmids` and the reaper spares it (the reaper keys on "no owning DB row,"
  not on `stopped` state, per ADR-0010 / WSX-04).

So a stopped workspace is, mechanically, already durable: same VMID, same disk, just
`status = stopped`. What is missing is only an explicit, queryable **intent** flag so
the operator can opt a workspace into being kept versus the default ephemeral churn,
and so future policy (idle auto-stop vs auto-destroy, UI affordances) can branch on
it.

Higher tiers were considered and explicitly deferred:

- **Snapshots (VM.Snapshot / storage snapshots):** point-in-time rollback. Needs a
  snapshot-capable storage backend and the `VM.Snapshot` Proxmox privilege the
  least-privilege `burrow@pve` role intentionally omits.
- **CRIU / suspend-to-disk:** preserve live process + scrollback state across a
  stop. Fragile under LXC, ties persistence to kernel/CRIU compatibility.

Neither is needed for "stop now, restart later with my files intact," and both add
real operational surface, so they are out of scope for v1.3 (deferred to v1.4+,
already recorded as WSX-05/06/07 in STATE).

## Decision

Adopt **Tier-1 persistence**: a per-workspace, opt-in `persistent` boolean that
marks a workspace as durable across stop/start, reusing the existing
`pct stop`/`pct start` lifecycle with NO new compute capability and NO snapshot.

- **`persistent` flag on `workspaces`.** Migration `003` adds
  `persistent INTEGER NOT NULL DEFAULT 0` (stored 0/1, surfaced as a `bool` DTO
  field). `DEFAULT 0` backfills existing v1.2 rows as ephemeral and is the locked
  default: a workspace is ephemeral unless the operator opts in at create time.
- **Tier-1 = plain stop/start, same VMID, disk preserved.** Persistence is a
  property of the row, not a new lifecycle state. A persistent workspace stops to
  `status = stopped` (LXC `pct stop`, disk intact, VMID held) and starts back to
  `running` on the SAME VMID. No new `ComputeProvider` ABC method, no `creating`
  flow change, no snapshot.
- **Create-time scope for v1.3.** `WorkspaceCreate.persistent` sets the flag once at
  create; there is no Tier-1 path that mutates `persistent` after create (a
  defensive `updateWorkspace` mapping is out of scope). The UI checkbox (Phase 13)
  drives this single create-time field.
- **Snapshots / CRIU / cross-reboot scrollback are deferred (v1.4+).** WSX-05/06/07
  remain future requirements gated on snapshot-capable storage, the `VM.Snapshot`
  privilege, and CRIU viability; none are introduced here.

## Consequences

- Persistence costs one column, one DTO field, and one create-saga thread: no new
  compute capability, no schema beyond the column, and no change to the reaper
  (which already spares any live-rowed VMID). The negative-control reaper test
  (Plan 04) locks that a persistent stopped workspace is never reaped.
- A persistent workspace holds its VMID and node disk while stopped, so it consumes
  pool capacity even when not running. That is the intended trade for durability;
  the operator opts in per workspace, and the default stays ephemeral so the pool
  is not silently filled.
- Because there is no snapshot, "restore" means "restart the same disk": in-memory
  process state and live terminal scrollback are NOT preserved by Tier-1 (scrollback
  restore is the separate worker-side WSX-03 / Phase 11 concern via tmux). Tier-1
  guarantees files-on-disk continuity, not live-session continuity.
- Explicit destroy still removes a persistent workspace: soft-deleting the row drops
  it from `live_vmids`, so the reaper reclaims the CT. Persistence protects the
  stop/start path, not an explicit teardown.

## Revisit trigger

A requirement for point-in-time rollback or live-session continuity across a stop
(which forces snapshots or CRIU and the storage/privilege work they need), or a
need to toggle `persistent` after create (which adds a mutation path beyond the
create-time-only v1.3 scope).
