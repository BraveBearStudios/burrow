<!-- SPDX-FileCopyrightText: 2026 Brave Bear Studios -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
---
phase: 01-control-plane-api
reviewed: 2026-06-10T00:00:00Z
depth: deep
files_reviewed: 18
files_reviewed_list:
  - api/services/workspaceService.py
  - api/lib/statemachine.py
  - api/lib/errors.py
  - api/lib/logging.py
  - api/lib/middleware.py
  - api/compute/proxmoxProvider.py
  - api/compute/provider.py
  - api/compute/fakeProvider.py
  - api/db/sqliteProvider.py
  - api/db/provider.py
  - api/db/migrations/002_vmid_unique.sql
  - api/routers/workspaces.py
  - api/routers/internal.py
  - api/routers/health.py
  - api/routers/templates.py
  - api/main.py
  - api/config.py
  - api/lib/envelope.py
findings:
  critical: 3
  warning: 6
  info: 3
  total: 12
status: findings
---

# Phase 1: Code Review Report — Control Plane API

**Reviewed:** 2026-06-10
**Depth:** deep
**Files Reviewed:** 18
**Status:** findings

## Summary

Reviewed the Phase-1 control-plane saga, state machine, providers, and bootconfig
surface adversarially. The architecture is sound and the test suite is unusually
thorough for the happy paths. The defects that matter are in the *failure* paths
the tests do not exercise: the compensation/landing sequence can leave a row stuck
in `creating` when a post-failure DB write itself fails; the VMID reservation race
is only closed for the single-threaded Fake, not for genuinely concurrent SQLite
writers (no `busy_timeout`, so the loser surfaces `OperationalError`, not the
retried `VmidTakenError`); and idempotent destroy is mis-classified for the
running-CT case. Several lower-severity robustness and contract issues follow.

## Critical Issues

### CR-01: Saga landing can leave a row stuck in `creating` if a compensation-path DB write fails

**File:** `api/services/workspaceService.py:129-133`
**Issue:** The `except` block runs three awaited operations in sequence —
`_compensate`, `logEvent("boot.error", ...)`, then `updateWorkspace(status="error")`.
If `logEvent` raises (DB hiccup, FK error, disk full, transient lock), the
`updateWorkspace(status="error")` call is never reached, so the row remains in
`creating` forever — exactly the Pitfall-4 failure the saga claims to prevent
("never stuck `creating`", SC-11). Worse, the `logEvent` exception *replaces* the
original boot exception as the propagated error, masking the real cause. The
status update must land *before* (or independently of) the best-effort event log,
and the landing itself must be guarded so a failure there cannot mask the original
exception.
**Fix:**
```python
except Exception:
    await self._compensate(payload.node, vmid)
    # Land the row in `error` FIRST and guard it — this is the SC-11 guarantee.
    try:
        await self.db.updateWorkspace(ws.id, {"status": "error"})
    except Exception:
        pass  # never mask the original boot failure
    try:
        await self.db.logEvent(ws.id, "boot.error", {"reason": _safe(exc)})
    except Exception:
        pass
    raise  # re-raise the ORIGINAL boot exception, not a logging error
```
(Capture the original exception explicitly, e.g. `except Exception as exc:` and
`raise exc`, so the guarded calls cannot rebind it.)

### CR-02: VMID reservation race is not closed under concurrent SQLite writers — loser raises `OperationalError`, not `VmidTakenError`

**File:** `api/services/workspaceService.py:151-159`, `api/db/sqliteProvider.py:62-64,128-139`
**Issue:** The retry loop only catches `VmidTakenError`, which is raised solely
when the INSERT reaches the partial-unique-index check and gets
`IntegrityError: UNIQUE constraint failed: workspaces.vmid`. But `_connect()`
opens a fresh `aiosqlite.connect()` per operation with **no `busy_timeout` and
default (rollback) journal mode**. Under genuinely concurrent create sagas, the
losing writer is blocked by the winner's held write lock and aiosqlite raises
`sqlite3.OperationalError: database is locked` *before* the unique constraint is
ever evaluated. That error is not an `IntegrityError`, is not mapped to
`VmidTakenError`, and is not caught by the retry loop — it propagates as an
uncaught 500 and aborts the saga with no compensation. The TOCTOU is therefore
only closed for the single-threaded Fake (whose docstring even warns "the Fake
masks the race"); the real concurrent path it is designed for is not robust. The
`test_vmid_reservation.py` suite confirms the constraint fires *serially* but
never drives two concurrent writers, so this gap is untested.
**Fix:** Set a busy timeout (and ideally WAL) on every connection so a blocked
writer waits for the lock and then hits the real uniqueness check, surfacing
`VmidTakenError`:
```python
async with aiosqlite.connect(self._database_path) as conn:
    await conn.execute("PRAGMA busy_timeout = 5000")
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA foreign_keys = ON")
    yield conn
```
Additionally widen the retry to treat a transient `OperationalError`
("database is locked") as a retryable loss, or document that WAL+busy_timeout is
the required configuration for the reservation guarantee to hold.

### CR-03: `destroyCt` is NOT idempotent for a running container — compensation can leave an orphan CT and a non-freed VMID

**File:** `api/compute/proxmoxProvider.py:180-189`, `api/services/workspaceService.py:171-187`
**Issue:** The compensation contract is "idempotent stop+destroy frees the VMID."
But Proxmox refuses to `DELETE` a *running* LXC and returns an error that is
**not** a 404 — `_is_not_found()` returns `False`, so `destroyCt` raises
`LxcNotReadyError`. In `_compensate`, `stopCt` is attempted first, but if the
clone half-completed and the CT is in a transient/locked state, `stopCt`'s
UPID-block can time out (raising, swallowed at line 182-183), leaving the CT
running; the subsequent `destroyCt` then fails on the running CT (raised,
swallowed at line 185-187). Result: an **orphan container** holding the VMID on
the node, while the DB row lands in `error` (keeping the same VMID reserved in the
active unique index). The VMID is leaked on both planes until manual intervention.
The "destroy is a no-op on a missing CT" reasoning only covers the *not-yet-cloned*
and *already-gone* cases, not the *cloned-but-running* case the saga can produce.
**Fix:** Make destroy force-stop (or pass Proxmox `force=1`) and, in compensation,
verify teardown rather than blindly swallowing. Minimally, in `destroyCt` treat a
"CT is running / locked" error by issuing a stop+retry, or call
`self._api.nodes(node).lxc(vmid).status.stop.post()` defensively before delete.
The compensation should not report success while a CT still exists on the node.

## Warnings

### WR-01: `mint_repo_credential` returns a single global, long-lived token for every repo — contradicting its own security contract

**File:** `api/services/workspaceService.py:260-282`, `api/config.py:75`
**Issue:** The docstring is emphatic: the returned value "MUST be short-lived and
single-repo-scoped, MUST NEVER be a long-lived PAT … and do NOT read a global,
broadly-scoped token." The implementation does exactly the forbidden thing: it
returns `settings.git_credential_token` — one static value loaded once from `.env`,
identical for every `repo`, never expiring, ignoring the `repo` argument entirely.
Every worker, for every repository, receives the same credential. If this is wired
to a real token before Phase 3 (the stated operator action), the bootconfig
endpoint hands a broadly-scoped, long-lived PAT to every LAN caller that can reach
`/internal/bootconfig/{vmid}`. The seam being "pluggable" does not make the v1
behavior safe; the gap is that the contract and the code disagree, inviting an
operator to drop a real PAT into `git_credential_token` and believe it is scoped.
**Fix:** Until a real per-repo issuer exists, treat a configured
`git_credential_token` as a hard misconfiguration for multi-repo use, or scope the
returned value (e.g. derive a per-request short-lived token). At minimum, fail
loudly / log a structured warning when a non-empty global token is served so the
"this is not actually repo-scoped" reality is visible, and tighten the docstring to
match what v1 actually does.

### WR-02: Per-workspace lock dict grows unbounded across the process lifetime

**File:** `api/services/workspaceService.py:91,285-291`
**Issue:** `_lock_for` inserts an `asyncio.Lock` keyed by workspace id on first use
and never removes it. Workspace ids are random UUIDs, and destroyed workspaces'
locks are retained forever, so `self._locks` grows monotonically for the life of
the process. For a long-running self-host instance churning workspaces this is an
unbounded memory growth (a slow leak), and the comment claiming it is "created
lazily per id" omits that it is never reclaimed.
**Fix:** Reclaim the lock on destroy (delete the key inside `destroyWorkspace`
after soft-delete, while holding it is not possible — instead pop it in a
`finally` once the workspace is terminal), or use a bounded/weak structure keyed by
id. A simple approach: after `softDeleteWorkspace`, `self._locks.pop(workspace_id,
None)` — the row is gone, so no future caller needs that lock.

### WR-03: `injectBootConfig` is a silent no-op — boot intent is never persisted, so the bootconfig endpoint serves stale/derived config

**File:** `api/services/workspaceService.py:117-118`, `api/compute/proxmoxProvider.py:156-160`
**Issue:** Saga step 3 calls `self.compute.injectBootConfig(vmid, self._boot_config(payload))`,
but the real provider's `injectBootConfig` is `return None` (and the Fake discards
it). The ABC docstring says the *DB write* persists the intent — but nothing in the
saga writes the `BootConfig` to the DB. The bootconfig router instead reconstructs
the payload from `settings.config_repo/config_branch` plus the workspace row's
`project_repo/project_branch`. This happens to match today only because
`_boot_config` reads the same `settings` values, but the "inject" step is dead: it
mutates nothing and provides no recoverability. If config_repo/branch ever differ
per-workspace or change between create and boot, the served config silently
diverges from what was "injected." This is a no-op masquerading as a saga step.
**Fix:** Either remove the dead `injectBootConfig` call and document that bootconfig
is fully derived at read time, or actually persist the `BootConfig` so the served
payload is the intent captured at create time (recoverability, SC-2). Do not leave a
saga step that claims to persist intent but writes nothing.

### WR-04: `usedVmids` parses `cluster/resources` without guarding malformed `vmid` values

**File:** `api/compute/proxmoxProvider.py:118-121`
**Issue:** `{int(r["vmid"]) for r in resources if "vmid" in r and start <= int(r["vmid"]) <= end}`
calls `int(r["vmid"])` twice per row with no guard. Proxmox `cluster/resources`
returns heterogeneous rows; a row with `vmid` present but non-numeric/None (storage,
sdn, or a future resource type that reuses the key) raises `ValueError`/`TypeError`,
which is not a `ComputeError` subclass and so escapes the seam as an uncaught 500
during the saga's pre-clone scan. The double `int()` call also evaluates the cast
twice unnecessarily.
**Fix:** Parse defensively:
```python
out: set[int] = set()
for r in resources:
    raw = r.get("vmid")
    if raw is None:
        continue
    try:
        v = int(raw)
    except (TypeError, ValueError):
        continue
    if start <= v <= end:
        out.add(v)
return out
```

### WR-05: `cloneCt` does not roll back the pool-add / net0 writes when the clone UPID later fails

**File:** `api/compute/proxmoxProvider.py:132-154`
**Issue:** `_do()` issues the clone POST, then immediately the pool-add PUT and the
net0 config PUT, and only afterwards does `_block(upid)` wait for the clone task to
actually complete. If the clone UPID ends non-OK (`TaskFailedError` at line 154),
the CT may be partially created and the pool/net0 mutations have already run against
a half-baked VMID. Compensation then relies on `destroyCt`, which (per CR-03) may
not cleanly remove a partial CT. The ordering "fire dependent config PUTs before
confirming the clone succeeded" widens the orphan window.
**Fix:** Block on the clone UPID *first*, confirm `exitstatus == "OK"`, and only
then issue the pool-add and net0 PUTs. That keeps the dependent mutations off a
clone that never completed and shrinks the partial-state surface compensation must
clean up.

### WR-06: `_block` default has no timeout and `Tasks.blocking_status` exitstatus `None` handling is ambiguous

**File:** `api/compute/proxmoxProvider.py:67-80`
**Issue:** `_block` treats only `status is None` as timeout and only
`exitstatus != "OK"` as failure. A task that completes but reports
`exitstatus = None` (Proxmox can return a status dict whose task is done but whose
`exitstatus` key is absent/None on certain error transitions) is correctly rejected
— good — but the error string `f"task {upid} exited {None!r}"` is indistinguishable
from a genuine non-OK exit, and a `status` dict that is present but still
`{"status": "running"}` (poller returned the last-seen running snapshot rather than
`None` on some proxmoxer versions) would pass the `None` check and then fail the
`exitstatus` check with a confusing message. The handling is *safe* (it raises) but
the diagnostics conflate three distinct failure modes (timeout, still-running,
non-OK), which will make real-infra triage harder.
**Fix:** Distinguish the cases explicitly: check `status.get("status") != "stopped"`
(still running / unknown) separately from a stopped-but-non-OK `exitstatus`, and
emit distinct messages so an operator can tell a timeout from a task error.

## Info

### IN-01: `_SECRET_PATTERNS` entropy backstop will redact legitimate non-secret identifiers

**File:** `api/services/workspaceService.py:56`
**Issue:** The backstop `\b[A-Za-z0-9_-]{32,}\b` redacts *any* 32+ char alnum run,
including UPIDs, long commit SHAs, base64 error fragments, and workspace ids — all
non-secret and useful for triage. This over-redaction is safe (fail-closed) but
will hollow out `boot.error` reasons in practice, reducing their diagnostic value.
**Fix:** Keep the backstop, but consider raising the threshold or anchoring it to
secret-shaped contexts (`token=`, `Authorization:`) so legitimate identifiers
survive while real opaque tokens are still caught.

### IN-02: `get_db()` constructs a new `SqliteProvider` per request, re-running the migration check each time

**File:** `api/main.py:108-114`, `api/db/sqliteProvider.py:48-51,96-98`
**Issue:** `get_db()` returns a fresh `SqliteProvider(settings)` on every request; its
`_migrated` flag is per-instance and starts `False`, so the first DB call of every
request hits `_ensure_migrated()` → `migrate()`, which opens a connection, ensures
the ledger table, and scans `schema_migrations`. It is idempotent and correct, but
it means a migration round-trip on every request's first DB touch instead of once
per process. (Out of strict v1 scope as performance, flagged only because it is a
correctness-adjacent surprise: the singleton pattern used for compute is
deliberately *not* used for db.)
**Fix:** Cache the db provider like the compute singleton, or hoist `migrate()` to
app startup so per-request DB calls skip the ledger scan.

### IN-03: `_source_ip_ok` compares against `lxc_ip` but cannot see proxies / X-Forwarded-For

**File:** `api/routers/internal.py:52-64`
**Issue:** The defense-in-depth source-IP check compares `request.client.host` to
the workspace's `lxc_ip`. Behind the documented nginx TLS terminator, `client.host`
is the proxy's address, not the worker's, so the check would reject every legitimate
caller if enabled in the real topology — making the "defense-in-depth" toggle a
foot-gun that silently 404s all boots. It is off by default and explicitly not
auth, so severity is Info, but the limitation (only meaningful when the API is hit
directly, not via the documented nginx hop) should be recorded next to the toggle.
**Fix:** Note in the docstring/`config.py` comment that `bootconfig_source_ip_check`
is only valid when the API is reached directly by workers (no intermediary proxy),
or have it honor a trusted `X-Forwarded-For` when a proxy is configured.

---

_Reviewed: 2026-06-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
