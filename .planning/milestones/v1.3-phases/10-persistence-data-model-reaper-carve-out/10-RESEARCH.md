<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 10: Persistence Data Model + Reaper Carve-out - Research

**Researched:** 2026-06-25
**Domain:** SQLite migration mechanics · orphan-reaper safety predicate · proxmoxer UPID/ResourceException mocking · Playwright e2e cleanup hardening
**Confidence:** HIGH (every claim verified against the live codebase or the installed proxmoxer 2.3.0 source)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Persistence semantics & API contract**
- `persistent` is an optional `bool = false` field on the `WorkspaceCreate` request body; default create stays ephemeral. Follows the established snake_case-DB → camelCase-JSON DTO pattern (CamelModel base, `model_dump(by_alias=True)`).
- Create-time-only for v1.3 Tier-1 (WSX-02 scope) — no PATCH toggle on an existing workspace this milestone.
- Stop/start mechanism for a persistent workspace: reuse the same VMID via the existing `pct stop`/`pct start` path (`stopCt`/`startCt`), disk preserved, **no snapshot**. ADR-0013 defers suspend/snapshot to v1.4+. Same DB row stays (not soft-deleted), same id/vmid, returns to `running` with disk intact.
- The `003` migration backfills existing v1.2 rows to `persistent=false` via column `DEFAULT 0`; a fresh DB and a migrated v1.2 DB converge to the same schema.
- The `settings` singleton (ADR-0011) is added in the same `003` migration, carrying `setupCompletedAt` for Phase 12 to consume. Kept behind the DbProvider seam.

**Reaper carve-out (safety-critical, WSX-04)**
- Orphan predicate keys on "no owning DB row" (VMID in pool AND unowned by any live row) — **never** on `stopped` state. Locked by WSX-04.
- Persistent **+ soft-delete** interaction: persistence protects a workspace across **stop→start only**, NOT across an explicit operator delete. A soft-deleted persistent workspace becomes orphan-eligible and its CT/VMID is reclaimable. (Delete is intentional teardown; persistence is not a delete-shield.)
- Negative-control regression test is RED-if-regressed: a persistent workspace in `stopped` state, run the reconcile/reap pass, assert the CT survives and the DB row is intact; the test fails if the predicate ever regresses to state-based reaping. Locked by SC3.
- The carve-out lives inside the existing reconciler predicate loop (a companion "persistent-owned" exclusion set), not a new service — keeps the single safety bound in one place.

**Test tiers (mocked-proxmoxer + 07r e2e)**
- The mocked-proxmoxer tier is a new integration-tier module (`api/tests/integration/mock_proxmox.py`) with factory functions producing real-shaped UPID async-task polling and `proxmoxer.core.ResourceException` error shapes. Promote to a shared pytest fixture only when a second consumer appears (YAGNI).
- It must exercise real UPID async-task polling (`running`→`stopped` task transitions) and `ResourceException` error shapes on the setup/persistence compute paths the Fake never triggers. Locked by SC4/TEST-01.
- It must land BEFORE any persistence-compute change (hard gate, STATE blockers v1.3 gate #2).
- W3 "two-Start-affordance" assertion: assert **both** Start entry points (the header Start button and the terminal-placeholder Start button) are present and functional after a stop.
- 07r e2e hardening: per-test workspace-id tracking, an `afterEach` that asserts the cleanup `DELETE` succeeds, and an order-independent suite. Locked by SC5/TEST-02.

### Claude's Discretion
- Exact module layout of the mocked-proxmoxer factories, internal naming, and test-case decomposition are at Claude's discretion within the patterns above.
- Whether the `persistent-owned` exclusion is computed as a set or an inline predicate branch — implementer's call, as long as the safety bound stays in the existing loop.

### Deferred Ideas (OUT OF SCOPE)
- PATCH/toggle of `persistent` on an existing workspace (post-create mutation) — out of Tier-1 scope.
- Snapshot / CRIU suspend / cross-reboot scrollback — deferred to v1.4+ (WSX-05/06/07).
- The persistent checkbox UI and create-form wiring — Phase 13.
- The setup wizard backend/UI (Phases 12/13), tmux scrollback (Phase 11).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WSX-02 | Operator can mark a workspace **persistent** at create time (default ephemeral); a persistent workspace survives stop→start with disk + DB row intact. | `003` migration adds `persistent` column DEFAULT 0; `WorkspaceCreate`/`Workspace` add `persistent: bool = False`; `sqliteProvider` INSERT/SELECT/`updateWorkspace` column-map threaded; create saga passes `persistent` into the reservation row. Stop/start ALREADY preserves the row + VMID (verified `stopWorkspace`/`startWorkspace` keep the same row, only flip `status`). NO new state, NO ComputeProvider change. |
| WSX-04 | Orphan reaper **never destroys a persistent stopped workspace** (predicate keys on "no owning row," not "stopped"), proven by a negative-control regression test. | The reaper predicate ALREADY keys on `vmid in live_vmids` (reconciler.py:98,108). A `stopped` persistent workspace has a live (non-soft-deleted) row, so its vmid is already in `live_vmids` and already spared. Phase 10's work is the **negative-control test** that LOCKS this + an explicit carve-out comment; the soft-delete-persistent path makes it orphan-eligible (no extra code, falls out of the existing predicate). |
| TEST-01 | Mocked-proxmoxer integration tier exercising real-shaped UPID async-task polling + `ResourceException` shapes. | New `api/tests/integration/mock_proxmox.py` factory module. proxmoxer 2.3.0 source verified: `Tasks.blocking_status` polls `prox.nodes(node).tasks(upid).status.get()` until `status=="stopped"`; UPID must decode to 9 colon segments; `ResourceException(status_code, status_message, content, errors, exit_code)`. Mock with `responses` (already a dep) is the established pattern (test_proxmox_provider.py). |
| TEST-02 | Stop/start e2e cleanup hardened (07r): per-test id tracking (W1), asserted cleanup DELETE (W2), two-Start-affordance assertion (W3). | `ui/tests/e2e/stop-start.spec.ts` ALREADY has W1 (createdIds tracking) and an `afterEach` DELETE. Gaps: W2 the afterEach must ASSERT the DELETE `.ok()`; W3 the round-trip test must assert BOTH Start affordances (header `TerminalPanel.tsx:376` + placeholder CTA `TerminalPanel.tsx:463`) present after stop. Order-independence already holds via id-scoped cleanup + unique names. |
</phase_requirements>

## Summary

Phase 10 is almost entirely **additive to an already-correct foundation**. Three of the
four requirements are mostly "lock what already works" rather than "build new behaviour":

1. **WSX-02 (persistence column + create flag):** a mechanical `003` migration plus a
   one-line model field plus three call-site edits in `sqliteProvider.py`. Stop/start
   already preserves the row and VMID — verified in `workspaceService.stopWorkspace`/
   `startWorkspace`, which only flip `status` and never soft-delete. No new lifecycle
   state, no `ComputeProvider` ABC change, no snapshot.

2. **WSX-04 (reaper carve-out):** the reaper predicate at `reconciler.py:108` ALREADY
   keys on `vmid in live_vmids` (live = non-soft-deleted rows), NOT on `stopped` state. A
   persistent stopped workspace keeps a live row, so its VMID is already in `live_vmids`
   and already spared. The real deliverable is the **negative-control regression test**
   (RED-if-regressed) plus an explicit carve-out comment, and confirming the
   soft-deleted-persistent path correctly becomes orphan-eligible (it does — a soft-deleted
   row drops out of `listWorkspaces()`, so its VMID leaves `live_vmids`).

3. **TEST-01 (mocked-proxmoxer tier):** a new `api/tests/integration/mock_proxmox.py`
   factory module backed by the `responses` library (already a dependency, already the
   established proxmoxer-mocking pattern in `test_proxmox_provider.py`). The proxmoxer 2.3.0
   source is fully verified below — `Tasks.blocking_status` polls a precise URL until
   `status=="stopped"`, and `ResourceException` has a precise constructor — so the factories
   can produce real-shaped UPID polling sequences and error shapes. This is a HARD GATE: it
   must land before any persistence-compute change.

4. **TEST-02 (07r e2e hardening):** `stop-start.spec.ts` already tracks ids (W1) and
   deletes them in `afterEach`. The gaps are narrow: assert the cleanup DELETE succeeded
   (W2) and add an explicit two-Start-affordance assertion after stop (W3).

**Primary recommendation:** Execute in this order — (1) `mock_proxmox.py` factory module +
its self-tests [TEST-01, the gate], (2) negative-control reaper test + carve-out comment
[WSX-04], (3) `003` migration + model field + provider edits + create-saga threading
[WSX-02], (4) e2e W2/W3 hardening [TEST-02]. Author ADR-0013 and ADR-0011 alongside the
migration work. Everything is CI-provable over the Fake + the new mocked-proxmoxer tier; no
real Proxmox.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `persistent` flag accept + validate | API / Backend (Pydantic `WorkspaceCreate`) | — | Server-side input validation (ASVS V5); the create body is operator input through `/api/v1/workspaces`. |
| `persistent` column + `settings` table | Database / Storage (`003` SQL + `sqliteProvider`) | — | Schema + the camelCase↔snake_case bridge live only in `sqliteProvider.py` (seam discipline, CLAUDE.md). |
| Stop/start durability (same VMID, disk preserved) | API / Backend (`WorkspaceService` + `ComputeProvider.stopCt/startCt`) | Compute (Proxmox `pct stop/start`) | Already-shipped lifecycle; persistence is a property of the row, not a new compute call. |
| Orphan-reaper safety predicate | API / Backend (`Reconciler._reap`) | Database (live-row lookup) + Compute (`listManagedCts`) | The single safety bound stays in one loop (CONTEXT); it reads both seams through ABCs only. |
| Mocked-proxmoxer test substrate | Test infrastructure (integration tier) | Compute (real `ProxmoxComputeProvider` under mocked HTTP) | Closes the structural Fake-vs-real gap; exercises the real provider's UPID/error code paths via `responses`. |
| Two-Start-affordance + cleanup e2e | Browser / Client (Playwright over vite preview) | API (cleanup DELETE) | UI affordances + server-truth cleanup are only real in Chromium over the Fake. |

## Standard Stack

### Core (all already installed — NO new packages for this phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aiosqlite` | 0.22.1 | The `003` migration runs through the existing ledger | Already the v1 self-host store; seam-confined to `sqliteProvider.py`. [VERIFIED: `uv pip show` in api/.venv] |
| `proxmoxer` | 2.3.0 | The real provider the mocked tier exercises | Already the only Proxmox client; `Tasks`/`ResourceException` shapes verified from installed source. [VERIFIED: api/.venv site-packages] |
| `responses` | 0.26.1 | Mock the requests-based proxmoxer HTTP leg | Already the established proxmoxer-mocking lib (`test_proxmox_provider.py`); `respx` only patches httpx and would never intercept proxmoxer. [VERIFIED: `uv pip show`] |
| `pytest` + `pytest-asyncio` | 9.0.3 / 1.4.0 | Test runner (`asyncio_mode = "auto"`) | Already configured in `pyproject.toml`. [VERIFIED: pyproject.toml] |
| `@playwright/test` | (ui) | The 07r e2e suite | Already the Tier-3 harness over vite preview + Fake + stub ttyd. [CITED: ui/tests/e2e/stop-start.spec.ts] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `respx` | 0.23.1 | Mock the httpx ttyd-health leg in the integration `conftest` | Only the ttyd leg (httpx); never the proxmoxer leg. [VERIFIED: `uv pip show`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `responses` for the proxmoxer mock | `respx` | `respx` patches httpx only; proxmoxer rides `requests`, so respx would never intercept it (documented as RESEARCH Pitfall 5 in `test_proxmox_provider.py`). REJECTED. |
| A new `settings_singleton` table-name | reuse `settings` (CONTEXT-locked) | Name `settings` is CONTEXT-locked and shared with Phase 12; do not invent an alternate. |
| Snapshot/suspend for persistence | plain `pct stop`/`start` (Tier-1) | Snapshot drags in storage-backend + `VM.Snapshot` priv + sprawl; CRIU suspend is broken for unprivileged LXC. CONTEXT-locked to Tier-1; ADR-0013 records the deferral. |

**Installation:** None required. All libraries are already in `api/pyproject.toml` and
`ui/package.json`. **Do not add dependencies for this phase** (CLAUDE.md: no new deps
without a concrete need; none exists here).

**Version verification:**
```bash
uv pip show proxmoxer responses respx aiosqlite pytest-asyncio   # all present
```
proxmoxer 2.3.0 confirmed at `api/.venv/Lib/site-packages/proxmoxer` (publish: 2.x line is
the current MIT-licensed maintained release).

## Package Legitimacy Audit

> **N/A — this phase installs NO external packages.** Every library it touches
> (`aiosqlite`, `proxmoxer`, `responses`, `respx`, `pytest`/`pytest-asyncio`,
> `@playwright/test`) is already a committed dependency in `api/pyproject.toml` /
> `ui/package.json`, vetted in prior phases. No registry resolution, no slopcheck pass, and
> no `npm view`/`pip index` lookup is required because there is nothing new to install.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none) | — | No new packages; audit not applicable. |

**Packages removed due to slopcheck [SLOP] verdict:** none (no installs).
**Packages flagged as suspicious [SUS]:** none (no installs).

## Architecture Patterns

### System Architecture Diagram

```
                    POST /api/v1/workspaces  { ..., persistent: true }
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │ WorkspaceCreate (Pydantic)│  persistent: bool = False  (new field)
                    │  CamelModel: camel↔snake  │
                    └────────────┬─────────────┘
                                 │ payload.persistent
                                 ▼
                    ┌──────────────────────────┐
                    │ WorkspaceService          │  create saga step 1:
                    │  .createWorkspace()       │  thread `persistent` into
                    │  ._reserve_vmid_and_row() │  the reservation INSERT dict
                    └────────────┬─────────────┘
                                 │
                                 ▼
              ┌────────────────────────────────────────┐
              │ DbProvider (ABC) → SqliteProvider       │  003 migration:
              │  createWorkspace INSERT (+persistent)   │   • ALTER workspaces ADD persistent DEFAULT 0
              │  SELECT _WORKSPACE_COLUMNS (+persistent)│   • CREATE TABLE settings (singleton)
              │  updateWorkspace column_map (+persistent)│  applied via schema_migrations ledger
              └────────────┬───────────────────────────┘
                           │ rows carry persistent
                           ▼
   ┌───────────────────────────────────────────────────────────────┐
   │ Reconciler._reap()   (SAFETY BOUND — single loop)             │
   │                                                               │
   │  live_vmids = { row.vmid for row in db.listWorkspaces()       │  ← live = non-soft-deleted
   │                 if row.vmid is not None }                     │     (a stopped persistent
   │  for (node, vmid) in managed:                                 │      ws keeps a live row →
   │     if vmid in live_vmids or vmid not in pool: continue  ─────┼──→  its vmid is ALREADY in
   │     destroyCt(node, vmid)   # orphan: NO owning row           │      live_vmids → SPARED.
   │                                                               │      Soft-deleted persistent
   │  (+ carve-out comment: persistence protects stop→start,       │      ws drops out of the list →
   │   NOT explicit delete; a stopped persistent ws is already     │      vmid leaves live_vmids →
   │   live-owned and never reaped — proven by negative-control)   │      becomes orphan-eligible.)
   └───────────────────────────────────────────────────────────────┘

   ── TEST SUBSTRATE (closes the Fake-vs-real gap) ──────────────────
   ProxmoxComputeProvider ── requests ──→ mock_proxmox.py factories
     stopCt/startCt/destroyCt            (via `responses`):
        └ _block(upid) polls            • clone/start/stop UPID → running→stopped task seq
          nodes(node).tasks(upid)       • ResourceException(status_code=…, content=…) shapes
          .status.get() until stopped   real-shaped UPID polling the Fake NEVER triggers
```

### Recommended structure (files this phase touches)

```
api/
├── db/
│   ├── migrations/
│   │   └── 003_persistent_and_settings.sql   # NEW — persistent col + settings table
│   ├── sqliteProvider.py                      # EDIT — column in INSERT/SELECT/update map
│   └── provider.py                            # (optional) settings getter/setter on ABC
├── models/
│   └── workspace.py                           # EDIT — persistent: bool = False on both DTOs
├── services/
│   ├── workspaceService.py                    # EDIT — thread persistent into reservation row
│   └── reconciler.py                          # EDIT — carve-out comment only (logic already correct)
└── tests/
    ├── integration/
    │   └── mock_proxmox.py                     # NEW — UPID + ResourceException factories (the gate)
    └── unit/
        └── test_reconciler.py                 # EDIT — add negative-control persistent test(s)
ui/
└── tests/e2e/
    └── stop-start.spec.ts                      # EDIT — W2 asserted DELETE + W3 two-affordance
docs/adr/
├── ADR-0011-setup-state-store.md               # NEW — settings singleton + setupCompletedAt
└── ADR-0013-persistence-model.md               # NEW — Tier-1 persistent flag; snapshots deferred
```

### Pattern 1: The `003` migration through the existing ledger

**What:** Drop a `003_*.sql` file into `api/db/migrations/`; the existing `migrate()` runner
(`sqliteProvider.py:87-114`) globs `*.sql` sorted by name, records each stem in the
`schema_migrations` ledger, and applies only unseen files via `conn.executescript()`. It is
idempotent and re-runnable. No code change to `migrate()` is needed.

**When to use:** Any schema change. This is the ONLY blessed schema-evolution mechanism.

**Example:**
```sql
-- Source: pattern from api/db/migrations/002_vmid_unique.sql + ledger in sqliteProvider.py:87-114
-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/003_persistent_and_settings.sql
-- WSX-02: opt-in persistence flag (default ephemeral). ADR-0013.
-- ADR-0011: singleton settings store carrying setupCompletedAt (Phase 12 consumes it).

-- A v1.2 DB backfills existing rows to persistent=false via the column DEFAULT 0,
-- so a fresh DB and a migrated DB converge to the same schema (CONTEXT-locked).
ALTER TABLE workspaces ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0;

-- Singleton settings store. The single-row invariant is enforced by a fixed PK (id=1)
-- + a CHECK so a second insert collides rather than silently creating a second config row.
CREATE TABLE settings (
  id               INTEGER PRIMARY KEY CHECK (id = 1),
  setupCompletedAt TEXT          -- ISO-8601 when setup wizard finished; NULL = unconfigured
);
INSERT INTO settings (id, setupCompletedAt) VALUES (1, NULL);
```

> **SQLite `ALTER TABLE ADD COLUMN` gotcha (verified against SQLite semantics):** a NOT NULL
> column added by `ALTER TABLE` MUST carry a non-NULL `DEFAULT` (SQLite rejects
> `ADD COLUMN ... NOT NULL` without a default on a non-empty table). `DEFAULT 0` satisfies
> this and is exactly the CONTEXT-locked backfill. Booleans are stored as INTEGER 0/1 in
> SQLite (no native bool); Pydantic coerces 0/1 → `bool` cleanly on read.

### Pattern 2: snake_case ↔ camelCase column threading (3 call sites)

**What:** The SQLite schema uses camelCase columns; Pydantic uses snake_case fields; the
bridge lives ONLY in `sqliteProvider.py`. The column name `persistent` happens to be
identical in both cases (single word), so the `AS` alias is a no-op — but it must still be
added to all three sites so the field round-trips.

**Sites to edit (verified line ranges):**
1. `_WORKSPACE_COLUMNS` (`sqliteProvider.py:37-42`) — add `persistent` to the SELECT list.
2. `createWorkspace` INSERT (`sqliteProvider.py:131-147`) — add `persistent` to the column
   list + the params dict (`data.get("persistent", False)`).
3. `updateWorkspace` `column_map` (`sqliteProvider.py:208-219`) — add `"persistent": "persistent"`
   if any update path ever sets it (Tier-1 is create-only, so this is optional/defensive).

```python
# Source: api/db/sqliteProvider.py:37-42 (extend in place)
_WORKSPACE_COLUMNS = (
    "id, name, status, vmid, node, persistent, "          # ← add persistent
    "lxcIp AS lxc_ip, projectRepo AS project_repo, projectBranch AS project_branch, "
    "pluginSet AS plugin_set, createdAt AS created_at, stoppedAt AS stopped_at, "
    "destroyedAt AS destroyed_at, deletedAt AS deleted_at"
)
```

```python
# models/workspace.py — add to BOTH DTOs (Workspace and WorkspaceCreate)
class Workspace(CamelModel):
    ...
    persistent: bool = False          # WSX-02; stored as INTEGER 0/1, coerced to bool

class WorkspaceCreate(CamelModel):
    ...
    persistent: bool = False          # opt-in; default ephemeral (CONTEXT-locked)
```

### Pattern 3: The reaper carve-out is already correct — lock it, don't rebuild it

**What:** `Reconciler._reap` (`reconciler.py:75-127`) computes
`live_vmids = {row.vmid for row in rows if row.vmid is not None}` from
`db.listWorkspaces()` — which **excludes soft-deleted rows** (`sqliteProvider.listWorkspaces`
filters `WHERE deletedAt IS NULL`). The orphan predicate is
`if vmid in live_vmids or vmid not in pool: continue` (line 108). This keys on
**ownership** (a live row exists), NOT on `status`. Therefore:

- A `stopped` **persistent** workspace keeps a live (non-soft-deleted) row → its VMID is in
  `live_vmids` → already spared. ✅ (This is WSX-04 already satisfied.)
- A `stopped` **ephemeral** workspace is ALSO spared by the same bound (CONTEXT: no
  auto-reap of stopped ephemeral this milestone — confirmed, the reaper never keys on
  `stopped`).
- A **soft-deleted persistent** workspace drops out of `listWorkspaces()` → its VMID leaves
  `live_vmids` → becomes orphan-eligible. ✅ (This is the CONTEXT-locked "delete is not a
  persistence shield" — it falls out of the existing predicate with NO extra code.)

**Phase 10's actual deliverable for WSX-04:**
1. Add a `persistent`-aware **carve-out comment** at line 108-109 making the safety bound's
   intent explicit (persistence protects stop→start, the live-row bound already covers it,
   delete intentionally removes that protection).
2. Add the **negative-control regression test(s)** (Pattern below).

**When to use:** Do NOT add a `status == "stopped"` branch, a `persistent` exclusion set, or a
new service. The existing single bound is the safety property; adding a parallel check would
create two sources of truth (CONTEXT explicitly wants the single bound in one loop).

### Anti-Patterns to Avoid
- **Adding a `persistent`/`stopped` branch to the reaper:** the predicate must stay
  ownership-keyed. A `status`-keyed branch is the exact regression the negative-control test
  guards against.
- **Hand-writing a second migration runner or a "if column exists" check:** the ledger
  (`schema_migrations`) is the single mechanism; Pitfall 6 (Plan 01-01) already burned a
  "skip if table exists" shortcut. Just drop the `.sql` file.
- **Using `respx` to mock proxmoxer:** respx patches httpx; proxmoxer rides requests. Use
  `responses`.
- **A second `settings` row:** the singleton invariant (`CHECK (id = 1)`) must hold; never
  `INSERT` a second row.
- **A bare-echo / shapeless proxmoxer mock:** the mock must produce a real 9-segment UPID and
  a `running`→`stopped` task transition, or it proves nothing the Fake doesn't already.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migration apply/track | A custom "has-column?" pragma check | The existing `schema_migrations` ledger (drop a `003_*.sql`) | Idempotent, ordered, already burned the shortcut in Pitfall 6. |
| Mocking proxmoxer's HTTP leg | A bespoke `ProxmoxAPI` subclass / monkeypatch | `responses` registering the exact task-status URLs | proxmoxer rides requests; `responses` intercepts it cleanly (established in `test_proxmox_provider.py`). |
| UPID task polling in the mock | A fake `Tasks` object | Register the `GET .../tasks/{upid}/status` response with `{"status":"stopped","exitstatus":"OK"}` | `Tasks.blocking_status` calls the real URL; matching the URL exercises the real `_block` code path. |
| Boolean storage in SQLite | A "true"/"false" TEXT column | `INTEGER NOT NULL DEFAULT 0` | SQLite has no bool; INTEGER 0/1 is canonical and Pydantic coerces it. |
| snake↔camel mapping for `persistent` | Per-field hand-mapping | `CamelModel` + the `_WORKSPACE_COLUMNS` alias list | Single source of truth (Plan 00-01 decision); `persistent` is single-word so the alias is identity. |
| e2e per-test isolation | A global DB wipe between tests | id-scoped `createdIds` + `afterEach` DELETE (already present) | Order-independent, parallel-safe; a broad wipe would race sibling tests. |

**Key insight:** This phase's risk is NOT missing infrastructure — it is *rebuilding
infrastructure that already works* and thereby creating a second source of truth for the
safety bound or the migration ledger. The discipline is "extend in place + lock with a test,"
not "add a new component."

## Runtime State Inventory

> Phase 10 is a schema + test phase against the Fake/mocked compute — there is **no real
> Proxmox, no live external service, no OS registration** touched. The inventory is included
> for rigor because it adds a DB column.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | The `workspaces` table gains a `persistent` column; the new `settings` table gains a singleton row. Existing v1.2 rows backfill to `persistent=0` via `DEFAULT 0`. | Data migration is the `ALTER TABLE` + `INSERT settings` in `003` — a code-delivered migration, not a manual data edit. No existing record needs a separate backfill pass (the DEFAULT handles it). |
| Live service config | **None.** No n8n, Datadog, Tailscale, Cloudflare, or similar. Burrow's only "live" surface is Proxmox, untouched in CI (Fake/mocked). Verified: no such integrations in `api/`. | None. |
| OS-registered state | **None.** No Task Scheduler / pm2 / systemd / launchd registration carries any string this phase renames. The reconciler runs as an in-process asyncio task (ADR-0010), not an OS unit. Verified by `services/reconciler.py` docstring + ADR-0010. | None. |
| Secrets / env vars | **None changed.** No new secret, no env-var rename. `settings.setupCompletedAt` is a DB column (not a secret) and is non-sensitive. The Proxmox token remains `.env`-only and untouched (Phase 12 concern). | None. |
| Build artifacts / installed packages | **None.** No new package, so no egg-info / lockfile / image-tag drift. `api/pyproject.toml` and `ui/package.json` are unchanged. | None. |

**Nothing found in categories Live-service/OS-registered/Secrets/Build-artifacts** — verified
by reading `services/reconciler.py`, `config.py` references, and confirming no new dependency
is added. The only state change is the additive DB schema delivered by `003`.

## Common Pitfalls

### Pitfall 1: The reaper regresses to `status`-based reaping
**What goes wrong:** A future edit "optimizes" the reaper by checking `status == "stopped"` or
adds a TTL that destroys stopped CTs — silently destroying a persistent stopped workspace's
disk (the v1.3 hard-gate hazard #1).
**Why it happens:** "Stopped looks idle/orphaned" is an intuitive but wrong heuristic; the
correct key is ownership (a live row), not state.
**How to avoid:** The negative-control regression test is RED-if-regressed: a persistent
`stopped` workspace with a live row + its CT present → run `reconcile_once()` → assert the CT
survives AND the row is intact. Plus the carve-out comment at the predicate.
**Warning signs:** Any new `status` or `persistent` reference inside `_reap`'s orphan branch;
any new "destroy stopped after N" setting.

### Pitfall 2: `ALTER TABLE ADD COLUMN NOT NULL` without a DEFAULT
**What goes wrong:** SQLite refuses `ALTER TABLE workspaces ADD COLUMN persistent INTEGER NOT NULL`
on a non-empty table with no default → the migration throws, the ledger never records `003`,
and every subsequent DB call retries-and-fails.
**Why it happens:** SQLite (unlike a fresh `CREATE TABLE`) cannot back-fill a NOT NULL column
without a value for existing rows.
**How to avoid:** Always `... NOT NULL DEFAULT 0`. This is also the CONTEXT-locked backfill.
**Warning signs:** Migration test fails only against a DB that already has rows (a fresh DB
masks it).

### Pitfall 3: Mocking proxmoxer with `respx` (wrong transport)
**What goes wrong:** The mock never intercepts the proxmoxer call (respx patches httpx;
proxmoxer rides requests), so the test either hits the network or fails confusingly.
**Why it happens:** Both libs exist in this repo (`respx` for the ttyd leg, `responses` for
proxmoxer); it is easy to grab the wrong one.
**How to avoid:** Use `responses` for the proxmoxer leg. Register the exact base URL
`https://{host}:8006/api2/json/...` (see `test_proxmox_provider.py:_BASE`).
**Warning signs:** A test that "passes" without registering any `responses.add`, or a
`ConnectionError` to a real host.

### Pitfall 4: A malformed UPID breaks `Tasks.blocking_status`
**What goes wrong:** `Tasks.decode_upid` asserts the UPID has exactly 9 colon-separated
segments starting with `UPID:` (verified in source). A mock returning a short/garbage UPID
raises `AssertionError("UPID is not in the correct format")` inside `_block`, not the error
the test intended.
**Why it happens:** UPIDs look opaque; it is tempting to use a placeholder like `"upid-123"`.
**How to avoid:** Use the established 9-segment shape:
`f"UPID:{node}:0000ABCD:00100000:64000000:vzstart:{vmid}:burrow@pve:"` (mirrors
`test_proxmox_provider.py:_CLONE_UPID/_STOP_UPID/_DESTROY_UPID`).
**Warning signs:** `AssertionError: UPID is not in the correct format` in a stop/start mock test.

### Pitfall 5: The mocked-proxmoxer tier lands AFTER the persistence-compute change
**What goes wrong:** The structural Fake-vs-real gap (the Fake never triggers UPID polling or
`ResourceException`) stays open while persistence-touching compute code is written, so a
real-only bug ships unnoticed (v1.3 hard-gate #2).
**Why it happens:** The mock feels like "just tests," easy to defer.
**How to avoid:** Plan ordering MUST place `mock_proxmox.py` + its self-tests as the FIRST
deliverable, gating the rest. (CONTEXT + STATE both lock this.)
**Warning signs:** A plan that writes `003`/model edits before the mock module exists.

### Pitfall 6: e2e cleanup DELETE failure swallowed (W2)
**What goes wrong:** The `afterEach` issues the DELETE but never checks `.ok()`, so a backend
that silently fails to clean up leaks Fake state across tests, eventually causing a flaky
order-dependent failure far from the root cause.
**Why it happens:** The current `afterEach` (`stop-start.spec.ts:86-94`) fires the DELETE
fire-and-forget.
**How to avoid:** Assert the response: a 200 (deleted) OR a 404 (already terminated through
the UI) is acceptable; anything else fails the test (W2). Keep id-scoped, never a broad wipe.
**Warning signs:** Intermittent failures that only appear when tests run in a particular order
or shard.

## Code Examples

### `mock_proxmox.py` — UPID + ResourceException factories (TEST-01)

```python
# Source: verified against proxmoxer 2.3.0 (api/.venv/.../proxmoxer/tools/tasks.py + core.py)
#         and the established responses pattern (api/tests/integration/test_proxmox_provider.py)
# SPDX headers required per CLAUDE.md.

import responses
from proxmoxer.core import ResourceException

_BASE = "https://{host}:8006/api2/json"

def make_upid(node: str, vmid: int, ttype: str) -> str:
    """A real-shaped 9-segment UPID (decode_upid asserts exactly 9 ':' fields)."""
    # UPID:node:pid:pstart:starttime:type:id:user:comment   (comment may be empty)
    return f"UPID:{node}:0000ABCD:00100000:64000000:{ttype}:{vmid}:burrow@pve:"

def register_task_poll(host: str, node: str, upid: str,
                       *, exitstatus: str = "OK",
                       running_polls: int = 1) -> None:
    """Register a running→stopped task transition that Tasks.blocking_status will poll.

    blocking_status loops GET nodes/{node}/tasks/{upid}/status until status=='stopped'.
    `responses` returns registered responses in order, so N 'running' responses then a
    'stopped' one models a real async task that completes after a few polls.
    """
    base = _BASE.format(host=host)
    url = f"{base}/nodes/{node}/tasks/{upid}/status"
    for _ in range(running_polls):
        responses.add(responses.GET, url,
                      json={"data": {"status": "running", "upid": upid}}, status=200)
    responses.add(responses.GET, url,
                  json={"data": {"status": "stopped", "exitstatus": exitstatus, "upid": upid}},
                  status=200)

def resource_exception(status_code: int, message: str, content: str = "") -> ResourceException:
    """A real proxmoxer.core.ResourceException shape the provider's defensive
    _is_not_found / _is_running_or_locked inspectors key on (status_code + message text)."""
    # Verified constructor: ResourceException(status_code, status_message, content, errors, exit_code)
    return ResourceException(status_code, message, content)
```

### Mock a stop→start round-trip on the real provider (TEST-01)

```python
# Source: pattern from test_proxmox_provider.py:test_destroy_running_ct_stops_then_destroys
@responses.activate
async def test_real_provider_start_blocks_on_upid_to_running() -> None:
    host, node, vmid = "pve1.local", "pve1", 201
    upid = make_upid(node, vmid, "vzstart")
    base = _BASE.format(host=host)
    responses.add(responses.POST, f"{base}/nodes/{node}/lxc/{vmid}/status/start",
                  json={"data": upid}, status=200)
    register_task_poll(host, node, upid, exitstatus="OK", running_polls=2)  # real polling

    task = await _provider(host).startCt(node, vmid)   # real ProxmoxComputeProvider
    assert task.status == "ok" and task.exitstatus == "OK" and task.upid == upid
```

### Negative-control reaper test — RED-if-regressed (WSX-04)

```python
# Source: pattern from test_reconciler.py:test_reap_spares_in_pool_ct_with_a_live_row
async def test_persistent_stopped_workspace_is_never_reaped(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    """WSX-04 hard gate: a persistent workspace in `stopped` state keeps its live row,
    so its VMID is in live_vmids and the orphan predicate spares it. This test fails
    (RED) the instant the predicate ever regresses to status-based reaping."""
    vmid = real_settings.worker_pool_start + 20
    ws = await db.createWorkspace({
        "name": "persistent-stopped", "node": "pve1",
        "project_repo": "git@example.com:acme/x.git",
        "vmid": vmid, "status": "stopped", "persistent": True,   # persistent + stopped
    })
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="persistent-stopped",
                                               node="pve1", running=False)

    await _reconciler(compute, db, now=datetime.now(timezone.utc)).reconcile_once()

    assert vmid in compute._containers, "a persistent stopped CT must survive the reap"
    row = await db.getWorkspace(ws.id)
    assert row is not None and row.status == "stopped" and row.persistent is True

async def test_soft_deleted_persistent_workspace_becomes_orphan_eligible(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    """CONTEXT-locked: persistence protects stop→start, NOT explicit delete. After a
    soft-delete the row leaves listWorkspaces() → its vmid leaves live_vmids → the CT
    is reclaimed by the reaper (no persistence shield against intentional teardown)."""
    vmid = real_settings.worker_pool_start + 21
    ws = await db.createWorkspace({
        "name": "persistent-deleted", "node": "pve1",
        "project_repo": "git@example.com:acme/x.git",
        "vmid": vmid, "status": "stopped", "persistent": True,
    })
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="persistent-deleted", node="pve1")
    await db.softDeleteWorkspace(ws.id)   # explicit teardown drops persistence protection

    await _reconciler(compute, db, now=datetime.now(timezone.utc)).reconcile_once()

    assert vmid not in compute._containers, "a soft-deleted persistent CT is reclaimable"
```

### e2e W2 (asserted DELETE) + W3 (two-affordance) hardening (TEST-02)

```typescript
// Source: extends ui/tests/e2e/stop-start.spec.ts:86-94 (afterEach) and :96-159 (round-trip)

// W2 — assert the cleanup DELETE succeeds (200 deleted | 404 already-terminated).
test.afterEach(async ({ request }) => {
  while (createdIds.length > 0) {
    const id = createdIds.pop();
    if (!id) continue;
    const res = await request.delete(`/api/v1/workspaces/${id}`);
    expect([200, 404]).toContain(res.status());   // W2: no silent cleanup failure
  }
});

// W3 — after Stop, assert BOTH Start affordances exist (header icon + placeholder CTA).
// (Inside the round-trip test, after "Workspace stopped" is visible.)
const startButtons = panel.getByRole("button", { name: "Start workspace" });
await expect(startButtons).toHaveCount(2);              // header (TerminalPanel.tsx:376)
const placeholder = panel.getByRole("status").filter({ hasText: "Workspace stopped" });
await expect(placeholder.getByRole("button", { name: "Start workspace" })).toBeVisible();  // CTA (:463)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| "Skip migration if workspaces table exists" | Ordered `schema_migrations` ledger applying each `*.sql` once | Plan 01-01 | `003` just drops a file; no runner change. |
| Mask the Proxmox race with the stateful Fake | Fake for happy-path + **mocked-proxmoxer tier** for UPID/error code paths | Phase 10 (this) | Closes the structural gap before persistence-compute work. |
| Fire-and-forget e2e cleanup | id-scoped tracked + asserted DELETE | Plan 07 (07r) finalized here | Order-independent, no silent leak. |

**Deprecated/outdated:**
- The tech-spec §9.3 ttyd snippet and the §7.1 schema are illustrative; the FROZEN
  migration ledger + the actual `001`/`002` SQL are the source of truth. Do not regenerate
  schema from §7.1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `settings` singleton invariant is best enforced with `id INTEGER PRIMARY KEY CHECK (id = 1)` + a single seeded row. | Pattern 1 | LOW — if the planner/ADR-0011 prefers a key/value `settings(key TEXT PRIMARY KEY, value TEXT)` shape instead, that is also valid; the column-vs-row shape is a discretion call. CONTEXT locks the *name* (`settings`) and the *field* (`setupCompletedAt`), not the row shape. Confirm in ADR-0011. |
| A2 | `updateWorkspace` does NOT need `persistent` in its `column_map` for v1.3 (create-only). | Pattern 2 | LOW — adding it is harmless and defensive; omitting it is fine because no Tier-1 path mutates `persistent`. |
| A3 | A `DbProvider` getter/setter for `settings.setupCompletedAt` is a Phase 12 concern, not Phase 10. Phase 10 only creates the table + seeds the row. | Architecture | LOW — Phase 12 (SETUP) consumes it; Phase 10 just lands the schema. If the planner wants the read/write seam now, it is a small additive ABC method, but YAGNI says defer (CONTEXT: "behind the DbProvider seam," table only). |

**No `[ASSUMED]` claims affect a locked decision, a compliance rule, a retention policy, or a
security control.** All three assumptions are shape/sequencing discretion that ADR-0011 / the
planner resolves cheaply.

## Open Questions

1. **`settings` table shape: singleton-columns vs key/value?**
   - What we know: CONTEXT locks the table name (`settings`), the field (`setupCompletedAt`),
     and that it lives behind the DbProvider seam and is shared with Phase 12.
   - What's unclear: whether ADR-0011 records a fixed-column singleton (`id=1` + named
     columns) or a generic key/value store. The singleton-column shape is simpler for a
     single known field; key/value is more extensible if Phase 12 adds many settings.
   - Recommendation: default to the singleton-column shape (Pattern 1) for KISS; let ADR-0011
     record the decision. Either round-trips through the seam identically.

2. **Does Phase 10 add a `DbProvider` read/write method for `setupCompletedAt` now?**
   - What we know: Phase 12 consumes it; Phase 10 must land the table.
   - What's unclear: whether the read/write seam method ships in 10 or 12.
   - Recommendation: land the table + seed in 10 (this phase's scope); defer the
     getter/setter to Phase 12 unless the planner wants a trivial additive method now (YAGNI).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `aiosqlite` | `003` migration | ✓ | 0.22.1 | — |
| `proxmoxer` | mocked-proxmoxer tier (real provider under mock) | ✓ | 2.3.0 | — |
| `responses` | proxmoxer HTTP mock | ✓ | 0.26.1 | — |
| `respx` | ttyd-health httpx mock (existing conftest) | ✓ | 0.23.1 | — |
| `pytest` + `pytest-asyncio` | test runner (`asyncio_mode=auto`) | ✓ | 9.0.3 / 1.4.0 | — |
| `@playwright/test` + Chromium | 07r e2e tier | ✓ (per prior phases' e2e gate) | ui dep | — |
| Real Proxmox | — | ✗ (by design) | — | Fake + mocked-proxmoxer tier; real infra is Phase 14 human UAT, NOT this phase. |

**Missing dependencies with no fallback:** none — every library this phase needs is already
installed and committed.
**Missing dependencies with fallback:** real Proxmox is intentionally absent; the mocked tier
+ Fake are the design substrate (CI never touches real Proxmox).

## Validation Architecture

> `workflow.nyquist_validation = true` (config.json) — this section is REQUIRED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework (api) | `pytest` 9.0.3 + `pytest-asyncio` 1.4.0, `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| Framework (ui) | `@playwright/test` (Tier-3) + `vitest` (Tier-2 component) |
| Config file | `api/pyproject.toml` `[tool.pytest.ini_options]`; `ui/playwright.config.ts` |
| Quick run (api unit) | `cd api && rtk pytest tests/unit/test_reconciler.py -x` |
| Quick run (api integration) | `cd api && rtk pytest tests/integration/ -x` |
| Full suite (api) | `cd api && rtk pytest` (then `rtk ruff check` + `rtk mypy .` per CLAUDE.md loop) |
| e2e (ui) | `cd ui && npm run e2e` (vite preview + Fake + stub ttyd) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | Real provider blocks on a real-shaped UPID `running`→`stopped` poll | integration | `rtk pytest tests/integration/test_mock_proxmox.py -x` | ❌ Wave 0 |
| TEST-01 | Real provider surfaces a `ResourceException` shape the Fake never triggers | integration | `rtk pytest tests/integration/test_mock_proxmox.py -x` | ❌ Wave 0 |
| WSX-04 | Persistent `stopped` workspace is NEVER reaped (negative control) | unit | `rtk pytest tests/unit/test_reconciler.py::test_persistent_stopped_workspace_is_never_reaped -x` | ⚠️ extend `test_reconciler.py` |
| WSX-04 | Soft-deleted persistent workspace BECOMES orphan-eligible | unit | `rtk pytest tests/unit/test_reconciler.py::test_soft_deleted_persistent_workspace_becomes_orphan_eligible -x` | ⚠️ extend `test_reconciler.py` |
| WSX-02 | `003` migration adds `persistent` (DEFAULT 0) + seeds `settings` singleton; fresh DB == migrated DB | unit/integration | `rtk pytest tests/unit/test_migrations.py -x` (or extend an existing migration test) | ❌ Wave 0 |
| WSX-02 | `persistent: true` on create round-trips DB→API as camelCase JSON | integration | `rtk pytest tests/integration/test_workspaces_api.py -x` (extend `_CREATE_BODY`) | ⚠️ extend |
| WSX-02 | A persistent workspace survives stop→start (same id/vmid, status running again) | integration | `rtk pytest tests/integration/test_workspaces_api.py::test_stop_then_start_round_trip -x` (assert persistent preserved) | ⚠️ extend |
| TEST-02 | Cleanup DELETE asserted ok (W2) | e2e | `cd ui && npm run e2e -- stop-start` | ⚠️ extend `stop-start.spec.ts` |
| TEST-02 | Both Start affordances present after stop (W3) | e2e | `cd ui && npm run e2e -- stop-start` | ⚠️ extend `stop-start.spec.ts` |

### Sampling Rate
- **Per task commit:** the targeted quick run for the file touched (e.g.
  `rtk pytest tests/unit/test_reconciler.py -x`), plus `rtk ruff check` + `rtk mypy .`
  (CLAUDE.md loop).
- **Per wave merge:** `cd api && rtk pytest` (full backend suite) — must be green.
- **Phase gate:** full `api` suite + `cd ui && npm run e2e` (07r) green before
  `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `api/tests/integration/mock_proxmox.py` — the factory MODULE (the hard gate; lands first).
- [ ] `api/tests/integration/test_mock_proxmox.py` — self-tests proving the factories drive the
      real provider's UPID + `ResourceException` paths (covers TEST-01).
- [ ] `api/tests/unit/test_migrations.py` — assert `003` applies, `persistent` defaults 0 on a
      pre-existing row, `settings` singleton seeded, fresh-DB == migrated-DB schema (covers WSX-02
      schema). *(If an existing migration test file is preferred, extend it instead.)*
- [ ] Extend `api/tests/unit/test_reconciler.py` — the two negative-control tests (WSX-04).
- [ ] Extend `api/tests/integration/test_workspaces_api.py` — `persistent` create round-trip +
      stop/start preserves persistent (WSX-02 behaviour).
- [ ] Extend `ui/tests/e2e/stop-start.spec.ts` — W2 asserted DELETE + W3 two-affordance.

*No new test framework install is needed — pytest/playwright/respx/responses are all present.*

## Security Domain

> `security_enforcement = true`, `security_asvs_level = 1`, `security_block_on = "high"`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | v1 is LAN-only, no-auth by design (CLAUDE.md security posture). Do not add auth assumptions. |
| V3 Session Management | no | No sessions in v1. |
| V4 Access Control | no | No multi-tenancy in v1 (hosted-path concern). |
| V5 Input Validation | **yes** | `persistent: bool` validated server-side by Pydantic `WorkspaceCreate` (CamelModel). A non-bool body is rejected at the boundary → 422, not a raw 500. The `003` migration uses a fixed literal `DEFAULT 0` (no interpolation). |
| V6 Cryptography | no | No new secret, no crypto. The Proxmox token (`.env`-only, validate-in-memory) is untouched — a Phase 12 concern. `settings.setupCompletedAt` is a non-sensitive timestamp. |
| V7 Logging/Redaction | **yes (inherited)** | The reaper already routes any exception text through `_safe()` and emits only the integer vmid in `reaper.destroyed` (verified `reconciler.py:113`). The negative-control test (`test_reaper_*_carries_no_secret` pattern) must keep proving no row field leaks into a `reaper.*` event. No new field (`persistent` is a bool) widens the leak surface. |

### Known Threat Patterns for {SQLite migration + reaper + mocked compute}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via migration / column value | Tampering | `003` is a static `.sql` literal (no interpolation); `persistent` flows through parameterized INSERT (`:persistent`) — never string-formatted. Verified: all `sqliteProvider` writes are bound params. |
| Destroying a persistent workspace's disk (data loss) | Denial of Service / Tampering | The ownership-keyed reaper bound + the RED-if-regressed negative-control test (WSX-04 hard gate). |
| Secret leaking into a `reaper.*` event when a new field is read | Information Disclosure | `_safe()` redaction + the existing `test_reaper_*_carries_no_secret` guard; `persistent` is a bool and carries no operator string. |
| `settings.setupCompletedAt` mistaken for a secret store | Information Disclosure | ADR-0011 records it as a non-sensitive timestamp only; the token stays `.env`-only (token-at-rest ADR avoided by design). |

**No `high`-severity security item blocks this phase.** The phase adds a validated boolean
column and a non-sensitive timestamp table; it introduces no new ingress, no secret, and no
auth surface. The one safety-critical control (the reaper bound) is data-loss prevention,
covered by the WSX-04 hard-gate test.

## Sources

### Primary (HIGH confidence)
- **Live codebase** (read in full this session): `api/db/sqliteProvider.py`,
  `api/db/provider.py`, `api/db/migrations/001_init.sql` + `002_vmid_unique.sql`,
  `api/services/reconciler.py`, `api/services/workspaceService.py`,
  `api/compute/proxmoxProvider.py` + `provider.py` + `fakeProvider.py`,
  `api/models/workspace.py` + `base.py`, `api/routers/workspaces.py`,
  `api/lib/statemachine.py`, `api/tests/unit/test_reconciler.py`,
  `api/tests/integration/test_proxmox_provider.py` + `test_workspaces_api.py` + `conftest.py`,
  `ui/tests/e2e/stop-start.spec.ts`, `ui/src/components/TerminalPanel.tsx`.
- **proxmoxer 2.3.0 installed source** (`api/.venv/Lib/site-packages/proxmoxer/`):
  `tools/tasks.py` (`Tasks.blocking_status` polls `nodes(node).tasks(upid).status.get()` until
  `status=="stopped"`; `decode_upid` asserts 9 colon segments), `core.py`
  (`ResourceException(status_code, status_message, content, errors=None, exit_code=None)`).
- `.planning/phases/10-.../10-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`,
  `.planning/config.json` (nyquist + security flags), `docs/tech-spec.md §7.1`,
  `docs/adr/ADR-0010-*.md` (ADR format).

### Secondary (MEDIUM confidence)
- SQLite `ALTER TABLE ADD COLUMN` NOT-NULL-requires-DEFAULT semantics (well-established
  SQLite behaviour; consistent with the repo's existing `002` partial-index approach).

### Tertiary (LOW confidence)
- None. Every claim is grounded in repo source or installed package source read this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library version confirmed via `uv pip show`; no new packages.
- Migration mechanics: HIGH — ledger + `001`/`002` read directly; `003` follows the identical pattern.
- Reaper carve-out: HIGH — predicate read line-by-line; the "already correct" finding is verified
  against `listWorkspaces` (filters soft-deleted) + `_reap` (keys on `live_vmids`).
- proxmoxer mock shapes: HIGH — `Tasks.blocking_status`, `decode_upid`, and `ResourceException`
  read from the installed 2.3.0 source.
- e2e hardening: HIGH — `stop-start.spec.ts` + the two Start affordances located by grep
  (TerminalPanel.tsx:376 header, :463 placeholder CTA).

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (stable; the only fast-moving surface is proxmoxer, pinned at 2.3.0)

## RESEARCH COMPLETE

**Phase:** 10 - Persistence Data Model + Reaper Carve-out
**Confidence:** HIGH

### Key Findings
- **WSX-04 is mostly "lock what already works":** the reaper predicate at `reconciler.py:108`
  already keys on `vmid in live_vmids` (ownership), never on `stopped` state, and
  `listWorkspaces()` excludes soft-deleted rows — so a persistent stopped workspace is already
  spared and a soft-deleted persistent workspace already becomes orphan-eligible. The deliverable
  is the RED-if-regressed negative-control test + a carve-out comment, NOT new reaper logic.
- **WSX-02 is additive + mechanical:** a `003` `ALTER TABLE ... ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0`
  + `settings` singleton through the existing `schema_migrations` ledger (drop a `.sql` file, no
  runner change), one `persistent: bool = False` field on both DTOs, and three `sqliteProvider`
  call-site edits. Stop/start already preserves the row + VMID (verified) — no new state, no
  `ComputeProvider` change, no snapshot.
- **TEST-01 mock is fully specified:** `Tasks.blocking_status` polls
  `nodes(node).tasks(upid).status.get()` until `status=="stopped"`; UPID needs 9 colon segments;
  `ResourceException(status_code, status_message, content, ...)`. Mock with `responses` (already a
  dep), mirroring `test_proxmox_provider.py`. This module is the HARD GATE — it lands first.
- **TEST-02 is two narrow edits:** the e2e suite already has W1 (id tracking) + an `afterEach`
  DELETE; add W2 (assert the DELETE `.ok()`) and W3 (assert both Start affordances —
  TerminalPanel.tsx:376 header + :463 placeholder CTA — after stop).
- **No new packages**; no real Proxmox; everything CI-provable over Fake + the new mocked tier.
  Author ADR-0013 (persistence) + ADR-0011 (settings singleton) alongside the migration.

### File Created
`.planning/phases/10-persistence-data-model-reaper-carve-out/10-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All versions confirmed via `uv pip show`; zero new deps. |
| Architecture | HIGH | Reaper predicate + migration ledger + stop/start lifecycle read directly from source. |
| Pitfalls | HIGH | proxmoxer UPID/ResourceException shapes + SQLite ADD-COLUMN semantics verified. |

### Open Questions
- `settings` table shape (singleton-columns vs key/value) — ADR-0011 decides; default to
  singleton-columns for KISS. Does not block planning.
- Whether the `DbProvider` getter/setter for `setupCompletedAt` ships in Phase 10 or 12 —
  recommend table-only in 10, seam method in 12 (YAGNI). Does not block planning.

### Ready for Planning
Research complete. The planner can create PLAN.md files with the locked execution order:
(1) `mock_proxmox.py` + self-tests [gate], (2) negative-control reaper tests + carve-out comment,
(3) `003` migration + model field + provider edits + create-saga threading + ADR-0013/0011,
(4) e2e W2/W3 hardening.
