---
phase: 10-persistence-data-model-reaper-carve-out
verified: 2026-06-25T12:02:28Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification (no prior VERIFICATION.md)
---

# Phase 10: Persistence Data Model + Reaper Carve-out Verification Report

**Phase Goal:** A workspace can be marked persistent at create time and durably survive stop→start, the orphan reaper provably never destroys a persistent stopped workspace, and the structural Fake-vs-real proxmoxer gap is closed by a mocked-proxmoxer integration tier — the shared foundation everything persistence-touching builds on.
**Verified:** 2026-06-25T12:02:28Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `003` migration adds `persistent` column (DEFAULT 0) + singleton `settings` table; migrate() applies it through the ledger; fresh DB and migrated v1.2 DB converge; idempotent re-run recovers (WR-03 fix) | VERIFIED | `003_persistent_and_settings.sql:11` (`ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0`), `:24-28` (`CREATE TABLE IF NOT EXISTS settings ... CHECK (id = 1)` + `INSERT OR IGNORE`). `migrate()` applies via `_apply_migration_file` (sqliteProvider.py:115,134-166) which catches "duplicate column name" and replays the idempotent remainder. Tests `test_fresh_and_migrated_converge`, `test_persistent_backfills_zero_on_preexisting_row`, `test_settings_singleton_seeded`, `test_settings_singleton_invariant_rejects_second_row`, `test_migrate_recovers_from_partial_003_apply` — all 5 PASS. |
| 2 | persistent=true then stop→start leaves same DB row (same id/vmid) running, disk intact; default create stays ephemeral | VERIFIED | `test_persistent_workspace_survives_stop_start_round_trip` (test_workspaces_api.py:60-86) asserts post-start `status=="running"`, `persistent is True`, `id==wid`, `vmid==created_vmid`. `test_default_create_is_ephemeral:54-57` asserts `persistent is False`. `persistent` threaded: model (workspace.py:32,48), provider SELECT (`_WORKSPACE_COLUMNS` :46) + INSERT (:176-186), saga base dict (workspaceService.py:287). All PASS. |
| 3 | Negative-control test proves reaper never destroys a persistent stopped workspace; predicate keys on ownership not `stopped` state; reconciler change is comment-only; RED if predicate regresses | VERIFIED | Predicate `reconciler.py:121` (`if vmid in live_vmids or vmid not in pool: continue`) is byte-identical to base — `git show 63208ad` added ONLY `#` comment lines (confirmed: zero non-comment additions). `test_persistent_stopped_workspace_is_never_reaped` + `test_soft_deleted_persistent_workspace_becomes_orphan_eligible` PASS. **RED-if-regressed empirically proven:** injecting a status-based reaping branch made `test_persistent_stopped_workspace_is_never_reaped` FAIL (`assert 220 in {}`); reconciler restored to committed state (no diff). |
| 4 | Mocked-proxmoxer integration tier exercises real-shaped UPID async-task polling + ResourceException; lands before persistence-compute | VERIFIED | `mock_proxmox.py` provides `make_upid` (9-segment), `register_task_poll` (running×N→stopped), `resource_exception` (verified `ResourceException(code,msg,content)` shape); imports `responses` + `ResourceException`, never `respx` (the 2 `respx` mentions are anti-pattern warnings in docstrings). `test_mock_proxmox.py` drives the REAL `ProxmoxComputeProvider` (5 references) through UPID poll (`test_real_provider_start_blocks_on_upid_running_to_stopped`), 404 idempotent (`..._destroy_is_idempotent_on_not_found`), and 500 stop-then-destroy retry (`..._destroy_running_ct_stops_then_destroys`). 4 tests PASS. Wave-1 dependency ordering: plans 03/04 `depends_on: [10-01]`. |
| 5 | Stop/start e2e cleanup hardened (07r): per-test id tracking, asserted cleanup DELETE, two-Start-affordance assertion, order-independent | VERIFIED | `stop-start.spec.ts`: W1 `createdIds` tracking (:37,76,88); W2 `expect([200, 404]).toContain(res.status())` in afterEach (:97); W3 `toHaveCount(2)` over `getByRole("button", {name:"Start workspace"})` (:142) + placeholder-scoped visibility (:146-148). **Suite executed live: 5 passed (23.7s), exit 0** — webserver logs show the asserted cleanup DELETE returning 200. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `api/db/migrations/003_persistent_and_settings.sql` | persistent column + settings singleton | VERIFIED | `ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0`; `CREATE TABLE IF NOT EXISTS settings` + `INSERT OR IGNORE` (WR-03-safe). |
| `api/models/workspace.py` | `persistent: bool = False` on both DTOs | VERIFIED | `Workspace.persistent` (:32), `WorkspaceCreate.persistent` (:48). |
| `api/db/sqliteProvider.py` | persistent threaded SELECT + INSERT; migrate() recovers | VERIFIED | `_WORKSPACE_COLUMNS:46`, INSERT :176-186, `_apply_migration_file` recovery :134-166, `_IMMUTABLE_FIELDS` guard :41,277-281 (WR-01). |
| `api/services/workspaceService.py` | `payload.persistent` into reservation | VERIFIED | base dict :287. |
| `api/services/reconciler.py` | carve-out COMMENT only, predicate unchanged | VERIFIED | comment :107-119; predicate :121 byte-identical (git-confirmed comment-only commit). |
| `api/tests/integration/mock_proxmox.py` | UPID + ResourceException factories | VERIFIED | 3 factories, `responses` substrate, no `respx`, WR-04 double-register guard. |
| `api/tests/integration/test_mock_proxmox.py` | self-tests over REAL provider | VERIFIED | 4 `@responses.activate` tests driving `ProxmoxComputeProvider`. |
| `api/tests/unit/test_migrations.py` | DEFAULT-0 backfill, singleton, convergence, partial-apply recovery | VERIFIED | 5 tests, all PASS. |
| `api/tests/unit/test_reconciler.py` | two negative-control tests | VERIFIED | both present + RED-if-regressed proven. |
| `api/tests/integration/test_workspaces_api.py` | create round-trip + stop→start | VERIFIED | 3 persistence tests, all PASS. |
| `docs/adr/ADR-0011-setup-state-store.md` | settings singleton + setupCompletedAt | VERIFIED | `## Decision` records singleton + `setupCompletedAt`. |
| `docs/adr/ADR-0013-persistence-model.md` | Tier-1; snapshots/CRIU deferred | VERIFIED | `## Decision` records Tier-1 opt-in, snapshot/CRIU deferred. |
| `ui/tests/e2e/stop-start.spec.ts` | W1+W2+W3 hardened, order-independent | VERIFIED | all three assertions present; suite ran green. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| workspaceService reservation base | sqliteProvider createWorkspace INSERT | `"persistent"` key → `:persistent` bind | WIRED | base dict :287 → INSERT bind :186 (`data.get("persistent", False)`). |
| 003 migration | sqliteProvider migrate() | schema_migrations ledger | WIRED | ledger loop :115-120 applies unseen stems; convergence test PASS. |
| test_mock_proxmox.py | proxmoxProvider.py | real `ProxmoxComputeProvider.startCt/destroyCt` under mocked HTTP | WIRED | `_provider(host)` builds real provider; UPID + ResourceException branches exercised. |
| test_reconciler.py | reconciler `_reap` predicate | `reconcile_once()` over persistent stopped row | WIRED | CT survives / reclaimed asserted; RED-if-regressed confirmed. |
| stop-start.spec.ts afterEach | DELETE /api/v1/workspaces/{id} | asserted status in [200,404] | WIRED | live run shows DELETE→200, assertion holds. |
| stop-start.spec.ts round-trip | TerminalPanel Start affordances | `Start workspace` count 2 | WIRED | TerminalPanel.tsx exposes the affordances; toHaveCount(2) passes live. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase-10 api tests pass | `pytest test_migrations test_reconciler test_mock_proxmox test_workspaces_api` | 32 passed | PASS |
| Full api suite (SUMMARY claim 216) | `pytest -q` | 216 passed, 11 warnings | PASS |
| Negative-control is RED-if-regressed | inject status-based reap → run Test A | FAILED as expected (`assert 220 in {}`); reconciler restored clean | PASS |
| Stop/start e2e suite | `playwright test stop-start` | 5 passed (23.7s), exit 0 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| WSX-02 | 10-03, 10-04 | Operator marks workspace persistent at create; survives stop→start with disk + row intact | SATISFIED | Truths #1, #2; stop→start round-trip test asserts same id/vmid + persistent. |
| WSX-04 | 10-04 | Orphan reaper never destroys a persistent stopped workspace (ownership-keyed), proven by negative-control test | SATISFIED | Truth #3; RED-if-regressed empirically proven; predicate comment-only diff. |
| TEST-01 | 10-01 | Mocked-proxmoxer integration tier exercising UPID async-task polling + ResourceException | SATISFIED | Truth #4; 4 tests drive REAL provider through both paths. |
| TEST-02 | 10-02 | Stop/start e2e cleanup hardened (W1 id tracking, W2 asserted DELETE, W3 two-affordance) | SATISFIED | Truth #5; all three present; suite green. |

No orphaned requirements: REQUIREMENTS.md maps exactly WSX-02, WSX-04, TEST-01, TEST-02 to Phase 10 (all marked Complete), and every ID is claimed by a plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No `TBD`/`FIXME`/`XXX` debt markers in any phase-10 source/test/ADR file | — | No unaudited debt. |

Note: IN-01 (REVIEW) flags the migration header's leading-slash path comment as a cosmetic, pre-existing convention (001 has the same). Not a blocker. WR-01/WR-02/WR-03/WR-04 from REVIEW all have dedicated fix commits (ba86497, 7616f52, 2321e26, 623b658) and were verified present in code.

### Human Verification Required

None. The phase is CI-provable over the Fake + the new mocked-proxmoxer tier (per ROADMAP "CI-provable: yes"). Real-Proxmox validation is by-design deferred to Phase 14 (ACC-01) and is NOT a Phase-10 gap. v1 LAN-only no-auth is by design, not a gap. The stop/start e2e suite was executed live (5 passed), so no visual/real-time human check remains open.

### Gaps Summary

No gaps. All 5 observable truths are VERIFIED with direct codebase evidence and live test execution. The full api suite (216 passed) and the stop-start e2e suite (5 passed) both run green. The safety-critical WSX-04 invariant was independently falsified-and-confirmed via a mutation test: injecting a status-based reaping regression made the negative-control test fail, proving it is genuinely RED-if-regressed; the reconciler was then restored to its committed (comment-only) state with no diff. All four REVIEW warnings (WR-01..WR-04) have applied fixes verified in code, including the WR-03 idempotent-re-run recovery that truth #1 explicitly requires.

---

_Verified: 2026-06-25T12:02:28Z_
_Verifier: Claude (gsd-verifier)_
