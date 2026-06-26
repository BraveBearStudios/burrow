# Phase 10: Persistence Data Model + Reaper Carve-out - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the shared persistence foundation for v1.3: a workspace can be
marked persistent at create time and durably survives stop→start (same DB row, same
id/vmid, disk intact), the orphan reaper provably never destroys a persistent stopped
workspace, and the structural Fake-vs-real proxmoxer gap is closed by a mocked-proxmoxer
integration tier. It also hardens the stop/start e2e cleanup (07r).

Requirements: WSX-02, WSX-04, TEST-01, TEST-02. CI-provable over the FakeComputeProvider
plus the new mocked-proxmoxer integration tier — no real Proxmox. ADRs authored in-phase:
ADR-0013 (persistence model — Tier-1 `persistent` flag; snapshots/suspend deferred) and
ADR-0011 (setup-state store — the `settings` singleton carrying `setupCompletedAt`,
shared with Phase 12).

Out of scope: the setup wizard backend/UI (Phases 12/13), tmux scrollback (Phase 11),
snapshots / CRIU suspend / cross-reboot scrollback (deferred v1.4+), and the persistent
checkbox UI (Phase 13 — this phase only adds the API/data-model surface).
</domain>

<decisions>
## Implementation Decisions

### Persistence semantics & API contract
- `persistent` is an optional `bool = false` field on the `WorkspaceCreate` request body;
  default create stays ephemeral. Follows the established snake_case-DB → camelCase-JSON
  DTO pattern (CamelModel base, `model_dump(by_alias=True)`).
- Create-time-only for v1.3 Tier-1 (WSX-02 scope) — no PATCH toggle on an existing
  workspace this milestone.
- Stop/start mechanism for a persistent workspace: reuse the same VMID via the existing
  `pct stop`/`pct start` path (`stopCt`/`startCt`), disk preserved, **no snapshot**.
  ADR-0013 defers suspend/snapshot to v1.4+. Same DB row stays (not soft-deleted),
  same id/vmid, returns to `running` with disk intact.
- The `003` migration backfills existing v1.2 rows to `persistent=false` via column
  `DEFAULT 0`; a fresh DB and a migrated v1.2 DB converge to the same schema.
- The `settings` singleton (ADR-0011) is added in the same `003` migration, carrying
  `setupCompletedAt` for Phase 12 to consume. Kept behind the DbProvider seam.

### Reaper carve-out (safety-critical, WSX-04)
- Orphan predicate keys on "no owning DB row" (VMID in pool AND unowned by any live
  row) — **never** on `stopped` state. Locked by WSX-04.
- Persistent **+ soft-delete** interaction: persistence protects a workspace across
  **stop→start only**, NOT across an explicit operator delete. A soft-deleted persistent
  workspace becomes orphan-eligible and its CT/VMID is reclaimable. (Delete is intentional
  teardown; persistence is not a delete-shield.)
- Negative-control regression test is RED-if-regressed: a persistent workspace in
  `stopped` state, run the reconcile/reap pass, assert the CT survives and the DB row is
  intact; the test fails if the predicate ever regresses to state-based reaping. Locked
  by SC3.
- The carve-out lives inside the existing reconciler predicate loop (a companion
  "persistent-owned" exclusion set), not a new service — keeps the single safety bound
  in one place.

### Test tiers (mocked-proxmoxer + 07r e2e)
- The mocked-proxmoxer tier is a new integration-tier module
  (`api/tests/integration/mock_proxmox.py`) with factory functions producing real-shaped
  UPID async-task polling and `proxmoxer.core.ResourceException` error shapes. Promote to
  a shared pytest fixture only when a second consumer appears (YAGNI).
- It must exercise real UPID async-task polling (`running`→`stopped` task transitions)
  and `ResourceException` error shapes on the setup/persistence compute paths the Fake
  never triggers. Locked by SC4/TEST-01.
- W3 "two-Start-affordance" assertion: assert **both** Start entry points (the header
  Start button and the terminal-placeholder Start button) are present and functional
  after a stop.
- 07r e2e hardening: per-test workspace-id tracking, an `afterEach` that asserts the
  cleanup `DELETE` succeeds, and an order-independent suite. Locked by SC5/TEST-02.

### Claude's Discretion
- Exact module layout of the mocked-proxmoxer factories, internal naming, and test-case
  decomposition are at Claude's discretion within the patterns above.
- Whether the `persistent-owned` exclusion is computed as a set or an inline predicate
  branch — implementer's call, as long as the safety bound stays in the existing loop.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- DbProvider ABC `api/db/provider.py:39-100`; SqliteProvider `api/db/sqliteProvider.py:45-310`.
- Migration ledger `api/db/sqliteProvider.py:87-114` — `schema_migrations` table, glob
  `*.sql` in `api/db/migrations/` sorted, idempotent apply via `conn.executescript()`.
- Existing migrations: `001_init.sql` (workspaces/events/templates), `002_vmid_unique.sql`
  (partial unique index on `vmid WHERE deletedAt IS NULL`).
- Workspace model `api/models/workspace.py:16-47`; `WorkspaceCreate` request DTO there.
- CamelModel base `api/models/base.py:19-26` (`alias_generator=to_camel`,
  `populate_by_name=True`) — the single snake→camel mapping mechanism.
- Create endpoint `api/routers/workspaces.py:26-33` — POST `/api/v1/workspaces`,
  envelope-wrapped via `respond(...)`.
- Reconciler reaper `api/services/reconciler.py:47-180`; orphan predicate at lines 75-114
  (`if vmid in live_vmids or vmid not in pool: continue`).
- ComputeProvider ABC `api/compute/provider.py:47-150`; FakeComputeProvider
  `api/compute/fakeProvider.py` (returns `ComputeTask(upid=None, status="ok")` instantly —
  no UPID polling, no `ResourceException`); ProxmoxComputeProvider
  `api/compute/proxmoxProvider.py:51-110` (synchronous proxmoxer + `to_thread`, UPID
  blocking lines 67-96).
- Integration fixtures `api/tests/integration/conftest.py:39-75` (real SQLite + Fake
  compute + respx-stubbed ttyd, `integration_client`).
- Reconciler unit tests `api/tests/unit/test_reconciler.py`.
- E2E stop/start `ui/tests/e2e/stop-start.spec.ts` (per-test tracking + cleanup ~lines 37-94).

### Established Patterns
- Migration: name `003_<description>.sql`, drop in `api/db/migrations/`, auto-recorded in
  ledger; re-runnable; `migrate()` invoked lazily on first DB method.
- snake→camel: DB columns camelCase in SQL; Pydantic fields snake_case; SELECT aliases
  `colX AS col_x`; `model_validate(dict(row))`; serialize `by_alias=True`.
- Envelope `{data, meta, error}` on every `/api/v1` route via `respond(...)`.
- Test tiers: unit (Fake compute, real SQLite tmp_path, injected `now`), integration
  (real app factory + httpx ASGITransport + Fake compute + respx ttyd), e2e (Playwright
  over vite preview).

### Integration Points
- `003_*.sql`: add `persistent` column to `workspaces` (camelCase `persistent`, `DEFAULT 0`)
  + the singleton `settings` table with `setupCompletedAt`.
- Workspace + WorkspaceCreate models: add `persistent: bool = False`.
- sqliteProvider: map `persistent` in INSERT (createWorkspace ~131-146), SELECT (~37-42),
  and updateWorkspace column_map (~208-219).
- Reconciler predicate loop (~108): exclude persistent-owned VMIDs from the reap.
- Create route (~28-33): thread `WorkspaceCreate.persistent` into the create saga.
- New `api/tests/integration/mock_proxmox.py`: UPID polling + ResourceException factories.
- `ui/tests/e2e/stop-start.spec.ts`: afterEach asserted DELETE + W3 two-affordance assertion.
</code_context>

<specifics>
## Specific Ideas

- ADR-0013 documents Tier-1 persistence = plain `pct stop`/`pct start` reuse of the same
  VMID, disk preserved, no snapshot/CRIU (those deferred to v1.4+).
- ADR-0011 documents the `settings` singleton as the setup-state store shared with Phase 12.
- The negative-control reaper test is a hard gate (STATE blockers, v1.3 gate #1).
- The mocked-proxmoxer tier must land BEFORE any persistence-compute change (STATE
  blockers, v1.3 gate #2).
</specifics>

<deferred>
## Deferred Ideas

- PATCH/toggle of `persistent` on an existing workspace (post-create mutation) — out of
  Tier-1 scope.
- Snapshot / CRIU suspend / cross-reboot scrollback — deferred to v1.4+ (WSX-05/06/07).
- The persistent checkbox UI and create-form wiring — Phase 13.
</deferred>
