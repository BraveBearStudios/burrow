---
phase: 10-persistence-data-model-reaper-carve-out
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - api/db/migrations/003_persistent_and_settings.sql
  - api/db/sqliteProvider.py
  - api/models/workspace.py
  - api/services/reconciler.py
  - api/services/workspaceService.py
  - api/tests/integration/mock_proxmox.py
  - api/tests/integration/test_mock_proxmox.py
  - api/tests/integration/test_workspaces_api.py
  - api/tests/unit/test_migrations.py
  - api/tests/unit/test_reconciler.py
  - docs/adr/ADR-0011-setup-state-store.md
  - docs/adr/ADR-0013-persistence-model.md
  - ui/tests/e2e/stop-start.spec.ts
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-25
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the Phase-10 persistence data model + setup-state store + reaper carve-out:
the 003 migration (`persistent` column + singleton `settings`), the three new
sqliteProvider call sites for `persistent`, the WSX-04 reaper carve-out, the
mocked-proxmoxer factories, and the supporting tests/ADRs.

The phase's safety-critical invariant (WSX-04) holds. I traced every executable
branch in `reconciler.py::_reap` and confirmed the orphan predicate keys ONLY on
ownership (`vmid in live_vmids`, sqliteProvider filters `WHERE deletedAt IS NULL`)
and NEVER on `stopped`/`persistent` state. The `reconciler.py` diff against the base
commit is verifiably comment-only (the executable body is byte-identical). The two
negative-control tests genuinely exercise the spare-vs-reclaim distinction. No
CRITICAL findings.

The `persistent` snake/camel handling is correct and consistent across all three
sqliteProvider sites: the INSERT writes the camelCase `persistent` column, the
`_WORKSPACE_COLUMNS` SELECT reads it back, and `Workspace.persistent: bool` coerces
the stored INTEGER. The `updateWorkspace` `column_map` intentionally omits
`persistent` (ADR-0013 fixes the flag as create-time-only) — see WR-01 for the
defensive gap that intent leaves. The migration's idempotency is ledger-guarded and
the singleton `CHECK (id = 1)` is correct. The mocked-proxmoxer factories produce
real-shaped 9-segment UPIDs and a verified-shape `ResourceException`.

Findings below are robustness/maintainability concerns, not correctness blockers.

## Warnings

### WR-01: `persistent` silently un-mappable in `updateWorkspace` — a future mutation path fails with an opaque `KeyError`

**File:** `api/db/sqliteProvider.py:210-227`
**Issue:** The `updateWorkspace` `column_map` deliberately omits `persistent`
(ADR-0013 scopes the flag to create-time only). That is fine *today*. The hazard is
the failure mode if a later phase (e.g. the Phase 13 UI toggle, or a hosted path)
ever calls `updateWorkspace(id, {"persistent": True})`: the loop hits
`column_map.get("persistent") is None` and raises `KeyError("unknown workspace
field: persistent")` — an internal-shaped error indistinguishable from a genuine
typo'd field, with no hint that `persistent` is *intentionally* immutable. ADR-0013's
"out of scope" rationale lives only in the ADR, not at the call site, so the guard
reads as an accidental omission rather than a deliberate policy.
**Fix:** Make the immutability explicit and self-documenting at the seam, so the
"create-time only" decision is enforced where it is violated, not in prose:
```python
# ADR-0013: `persistent` is create-time only in v1.3 — never mutable post-create.
_IMMUTABLE_FIELDS = {"persistent"}
...
for field_name, value in updates.items():
    if field_name in _IMMUTABLE_FIELDS:
        raise ValueError(f"{field_name} is immutable after create (ADR-0013)")
    column = column_map.get(field_name)
    if column is None:
        raise KeyError(f"unknown workspace field: {field_name}")
```

### WR-02: `createWorkspace` swallows ANY `OperationalError` containing "database is locked" as `VmidTakenError`, masking unrelated lock failures

**File:** `api/db/sqliteProvider.py:162-173`
**Issue:** The `except aiosqlite.OperationalError` branch substring-matches
`"database is locked"` and re-raises it as the retryable `VmidTakenError`. The
docstring justifies this for the VMID-reservation INSERT race, but the handler wraps
the *entire* INSERT statement. A "database is locked" raised for a reason unrelated
to VMID contention (e.g. an unrelated long-held write lock from another subsystem, a
mis-tuned `busy_timeout` under real concurrency) is laundered into the saga's bounded
retry loop (`workspaceService.py:289-302`). The service then re-scans and retries up
to 10 times against a DB that is genuinely locked for a different reason, and finally
surfaces `NoFreeVmidError` — a misleading "pool exhausted" error for what is actually
a lock-contention/IO problem. The `IntegrityError` branch above it is precise
(`"workspaces.vmid" in str(exc)`); the `OperationalError` branch is not.
**Fix:** This is a documented v1 trade (v1 assumes `--workers 1`, so genuine
cross-process contention is rare), so it is a WARNING not a BLOCKER — but the
laundering should at least be observable. Log the raw `OperationalError` at WARNING
before re-raising as `VmidTakenError`, so a real lock problem is not silently
re-spun as pool exhaustion:
```python
if "database is locked" in str(exc).lower():
    logger.warning("create INSERT hit a lock; treating as lost-race", exc_info=False)
    raise VmidTakenError(str(exc)) from exc
```

### WR-03: 003 migration is non-atomic within `executescript`; a mid-migration failure leaves the schema half-applied and unledgered

**File:** `api/db/migrations/003_persistent_and_settings.sql:11-22` (driven by
`api/db/sqliteProvider.py:107-113`)
**Issue:** `migrate()` runs each file via `conn.executescript(...)`, which issues an
implicit `COMMIT` before executing the script and does NOT wrap the script's
statements in a single transaction. In 003 the statements are: (1) `ALTER TABLE ...
ADD COLUMN persistent`, (2) `CREATE TABLE settings`, (3) `INSERT INTO settings`. If
(2) or (3) fails *after* (1) commits (e.g. a partially-pre-existing `settings` table
on a manually-touched DB, or an IO error between statements), the `persistent` column
is durably added but the ledger row for `003` is NEVER inserted (that INSERT and the
final `conn.commit()` are at `sqliteProvider.py:112-113`, after the `executescript`
returns). A subsequent `migrate()` re-runs 003 from the top and the `ALTER TABLE ...
ADD COLUMN persistent` now fails with "duplicate column name", wedging migration
permanently. The `test_migrations.py` suite only covers the all-or-nothing success
path; the partial-failure path is untested.
**Fix:** Make the column-add idempotent-safe and/or guard the table create so a
re-run after a partial apply is recoverable. SQLite cannot do `ADD COLUMN IF NOT
EXISTS`, so the robust option is `CREATE TABLE IF NOT EXISTS settings` plus an
`INSERT OR IGNORE` for the seed row, and to treat the column-add re-run defensively
(catch "duplicate column" in `migrate()` for an already-applied-but-unledgered file).
At minimum, add a regression test that simulates a partial 003 apply (column added,
ledger row missing) and asserts `migrate()` recovers rather than wedges.

### WR-04: `register_task_poll` mutates module-global `responses` registry state; multi-UPID tests rely on undocumented registration-order coupling

**File:** `api/tests/integration/mock_proxmox.py:47-77` (consumed by
`api/tests/integration/test_mock_proxmox.py:124-160`)
**Issue:** `register_task_poll` registers GETs against
`/nodes/{node}/tasks/{upid}/status` keyed only by `upid`. In
`test_real_provider_destroy_running_ct_stops_then_destroys` two different UPIDs
(`stop_upid`, `destroy_upid`) are registered, and the test's correctness depends on
`responses` replaying *per-URL* in registration order. Because the two UPIDs produce
distinct URLs, this happens to be safe — but the factory gives no guard against a
future test that reuses the same UPID across two `register_task_poll` calls, which
would silently interleave the running/stopped bodies and produce a confusing
mis-poll. The coupling (replay order within a URL, plus the `running_polls` count
matching the provider's poll cadence) is load-bearing but implicit.
**Fix:** Document the per-URL ordering contract in the `register_task_poll` docstring
and assert distinct UPIDs are not double-registered, or accept an explicit
`assert_all_requests_are_fired`-style check in the consuming tests so an unconsumed
or mis-ordered registration fails loudly rather than passing on accidental URL
distinctness.

## Info

### IN-01: 003 migration header path comment uses a leading-slash absolute path that does not match the repo layout

**File:** `api/db/migrations/003_persistent_and_settings.sql:3`
**Issue:** The header reads `-- Migrations: /api/db/migrations/003_persistent_and_settings.sql`.
The leading slash implies a filesystem-root path; the file lives at
`api/db/migrations/...` relative to the repo root. 001 has the identical
leading-slash style (`001_init.sql:3`), so this is a consistent-but-wrong convention
rather than a new defect.
**Fix:** Drop the leading slash (`-- Migrations: api/db/migrations/003_...`) for
accuracy, or remove the redundant self-referential path comment entirely.

### IN-02: `Workspace.persistent` declared after the nullable `*_at` fields, breaking the otherwise column-order field layout

**File:** `api/models/workspace.py:32`
**Issue:** Every other field on `Workspace` follows the `workspaces` table column
order (id → name → status → … → deleted_at). `persistent` is appended *after*
`deleted_at` with an inline default, while the 003 migration adds the column
physically *before* `lxcIp` is irrelevant (ALTER appends it last in SQLite anyway),
but the model field order now no longer mirrors the logical schema grouping
(`persistent` is a core durability attribute, not a trailing timestamp). Purely a
readability nit — `populate_by_name` makes field order irrelevant to mapping
correctness.
**Fix:** Optional: move `persistent: bool = False` up next to `status` (the other
core lifecycle attribute) for readability. No behavioral change.

### IN-03: `_WORKSPACE_COLUMNS` and the INSERT column list duplicate the schema shape in three places

**File:** `api/db/sqliteProvider.py:37-42, 132-148, 210-221`
**Issue:** The `persistent` column now appears in three hand-maintained lists: the
SELECT projection (`_WORKSPACE_COLUMNS`), the INSERT column list + VALUES binds, and
(by deliberate omission) the `updateWorkspace` `column_map`. Adding the next column
means editing all three in lockstep, with no compile-time or test-time check that
they agree. The `test_fresh_and_migrated_converge` test catches a *missing migration
column* but not a column present in the schema yet absent from the SELECT projection
(which would simply never surface on the DTO).
**Fix:** Out of scope for this phase, but worth a follow-up: derive the projection
from the model field names, or add a test that asserts every non-`deleted`
`workspaces` column appears in `_WORKSPACE_COLUMNS`. Tracking note only.

### IN-04: `make_upid` hardcodes `burrow@pve` userinfo in the UPID comment segment

**File:** `api/tests/integration/mock_proxmox.py:44`
**Issue:** `make_upid` embeds `burrow@pve` as the user segment. This matches the
`_Settings` stub's `proxmox_user` placeholder and is non-sensitive (a role name, not
a secret), so it does not violate the no-secrets-in-fixtures rule. Flagged only for
consistency: the user segment is fixed regardless of caller, so a test asserting on
the user field would be coupled to this constant.
**Fix:** None required. If a future test varies the user, thread it as a parameter.

### IN-05: `test_settings_singleton_invariant_rejects_second_row` leaves the first failed transaction open before the second assertion

**File:** `api/tests/unit/test_migrations.py:105-117`
**Issue:** Both `INSERT` attempts raise `aiosqlite.IntegrityError` at `execute()`
time (PRIMARY KEY collision, then CHECK collision), so the `await conn.commit()` line
inside each `pytest.raises` block never runs. SQLite statement-rolls-back the failed
INSERT but keeps the transaction open across the two blocks. The test passes because
each INSERT fails independently on its own constraint, but it relies on SQLite's
implicit per-statement rollback rather than an explicit `await conn.rollback()`
between the two assertions. A reader could reasonably misread the second `IntegrityError`
as proving the CHECK while it is partly an artifact of the still-open transaction.
**Fix:** Add `await conn.rollback()` between the two `pytest.raises` blocks (or use
two separate connections) so each assertion proves exactly one constraint in
isolation. Test-only clarity; no production impact.

---

_Reviewed: 2026-06-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
