<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 10: Persistence Data Model + Reaper Carve-out - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 11 (4 NEW, 5 MODIFY, 2 NEW ADR docs)
**Analogs found:** 11 / 11 (every file has an in-repo analog — this phase is "extend in place + lock with a test")

> Planner note: RESEARCH.md already maps most analogs with file:line and carries
> copy-ready snippets in its "Code Examples" section. This map verifies every analog
> against the live repo, fixes the exact line ranges, and pins the load-bearing
> excerpts so each plan action can copy from a real file, not RESEARCH prose.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/db/migrations/003_persistent_and_settings.sql` | migration | DDL / schema | `api/db/migrations/002_vmid_unique.sql` + `001_init.sql` | exact |
| `api/models/workspace.py` (MODIFY) | model | request-response DTO | itself (`Workspace` + `WorkspaceCreate` in place) | exact |
| `api/db/sqliteProvider.py` (MODIFY) | provider / data-access | CRUD column-map | itself (3 in-place call sites) | exact |
| `api/services/workspaceService.py` (MODIFY) | service | request-response saga | `_reserve_vmid_and_row` `base` dict (in place) | exact |
| `api/services/reconciler.py` (MODIFY) | service | event-driven sweep | itself, predicate loop ~line 108 (comment only) | exact |
| `api/tests/integration/mock_proxmox.py` (NEW) | test fixture / factory | request-response (mocked HTTP) | `api/tests/integration/test_proxmox_provider.py` | exact (same `responses` substrate) |
| `api/tests/integration/test_mock_proxmox.py` (NEW) | test | request-response (mocked HTTP) | `test_proxmox_provider.py::test_destroy_running_ct_stops_then_destroys` | exact |
| `api/tests/unit/test_reconciler.py` (MODIFY) | test | event-driven sweep | `test_reconciler.py::test_reap_spares_in_pool_ct_with_a_live_row` | exact |
| `api/tests/integration/test_workspaces_api.py` (MODIFY) | test | request-response | `test_stop_then_start_round_trip` + `_CREATE_BODY` | exact |
| `ui/tests/e2e/stop-start.spec.ts` (MODIFY) | test (e2e) | request-response | itself (`afterEach` + round-trip placeholder block) | exact |
| `docs/adr/ADR-0011-*.md` + `docs/adr/ADR-0013-*.md` (NEW) | doc (ADR) | n/a | `docs/adr/ADR-0010-in-process-reconciler-and-capacity-lock.md` | exact (format) |

**Execution-order gate (CONTEXT + STATE-locked):** `mock_proxmox.py` + `test_mock_proxmox.py`
land FIRST (the hard gate), then the negative-control reaper tests + carve-out comment, then
the `003` migration + model/provider/saga edits + ADRs, then the e2e W2/W3 hardening.

## Pattern Assignments

### `api/db/migrations/003_persistent_and_settings.sql` (NEW — migration, DDL)

**Analog:** `api/db/migrations/002_vmid_unique.sql` (header + idempotent DDL) and
`api/db/migrations/001_init.sql` (CREATE TABLE shape, camelCase columns, seed INSERT).

**SPDX + migration header** — copy from `002_vmid_unique.sql:1-4`:
```sql
-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/003_persistent_and_settings.sql
```

**Column-add + seed pattern** — the `001_init.sql` columns are camelCase with NOT NULL +
DEFAULT (`api/db/migrations/001_init.sql:5-20`); the `ALTER` must carry a non-NULL DEFAULT
(SQLite rejects `ADD COLUMN ... NOT NULL` without one on a non-empty table — RESEARCH Pitfall 2).
The seed-INSERT idiom is `001_init.sql:40` (`INSERT INTO templates (...) VALUES (...)`):
```sql
ALTER TABLE workspaces ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0;

CREATE TABLE settings (
  id               INTEGER PRIMARY KEY CHECK (id = 1),
  setupCompletedAt TEXT          -- ISO-8601 when setup finished; NULL = unconfigured
);
INSERT INTO settings (id, setupCompletedAt) VALUES (1, NULL);
```

**Ledger note (no code change):** the runner `migrate()` (`sqliteProvider.py:87-114`) globs
`*.sql` sorted, records each stem in `schema_migrations`, applies unseen files via
`conn.executescript()`. Dropping `003_*.sql` is the ONLY action — do NOT touch `migrate()`,
do NOT add a "column exists?" check (RESEARCH anti-pattern; Pitfall 6 already burned that).
`settings` table shape (singleton-column vs key/value) is ADR-0011's call — RESEARCH A1
recommends the singleton-column shape shown above for KISS.

---

### `api/models/workspace.py` (MODIFY — model, request-response DTO)

**Analog:** itself — both DTOs already inherit `CamelModel`; add one field to each.
`CamelModel` (`api/models/base.py:19-26`) is the single snake→camel mechanism
(`alias_generator=to_camel`, `populate_by_name=True`, `from_attributes=True`).

**Field add** — `Workspace` ends at `api/models/workspace.py:31` (`deleted_at: str | None`);
`WorkspaceCreate` ends at `:46` (`node: str | None = None`). Add to BOTH:
```python
class Workspace(CamelModel):          # api/models/workspace.py:16-31
    ...
    persistent: bool = False          # WSX-02; stored INTEGER 0/1, Pydantic coerces to bool

class WorkspaceCreate(CamelModel):    # api/models/workspace.py:34-46
    ...
    persistent: bool = False          # opt-in; default ephemeral (CONTEXT-locked)
```
`persistent` is single-word, so the camel alias is identity (`persistent` ↔ `persistent`) —
no SELECT `AS` aliasing needed for it (unlike `lxc_ip AS lxcIp`).

---

### `api/db/sqliteProvider.py` (MODIFY — provider, CRUD column-map)

**Analog:** itself — three in-place call sites that already thread every other column.

**Site 1 — `_WORKSPACE_COLUMNS` SELECT list** (`api/db/sqliteProvider.py:37-42`). Add
`persistent` to the bare (un-aliased) leading group, since the column name equals the field:
```python
_WORKSPACE_COLUMNS = (
    "id, name, status, vmid, node, persistent, "          # ← add persistent (identity alias)
    "lxcIp AS lxc_ip, projectRepo AS project_repo, projectBranch AS project_branch, "
    "pluginSet AS plugin_set, createdAt AS created_at, stoppedAt AS stopped_at, "
    "destroyedAt AS destroyed_at, deletedAt AS deleted_at"
)
```

**Site 2 — `createWorkspace` INSERT** (`api/db/sqliteProvider.py:131-147`). The INSERT lists
columns then binds a params dict; add `persistent` to both, defaulting false (mirrors the
existing `data.get("plugin_set", "default")` idiom):
```python
await conn.execute(
    "INSERT INTO workspaces "
    "(id, name, status, vmid, node, persistent, lxcIp, projectRepo, projectBranch, pluginSet) "
    "VALUES (:id, :name, :status, :vmid, :node, :persistent, :lxcIp, "
    ":projectRepo, :projectBranch, :pluginSet)",
    {
        ...
        "persistent": data.get("persistent", False),   # ← add; SQLite stores bool as 0/1
        ...
    },
)
```
> The `except aiosqlite.IntegrityError` / `OperationalError` blocks
> (`sqliteProvider.py:148-171`) are the VMID-race arbiter — DO NOT modify them; `persistent`
> rides through the same parameterized INSERT untouched.

**Site 3 — `updateWorkspace` `column_map`** (`api/db/sqliteProvider.py:208-219`). OPTIONAL /
defensive per RESEARCH A2 (Tier-1 is create-only; no path mutates `persistent`). If added:
```python
column_map = {
    ...
    "persistent": "persistent",   # optional/defensive — no Tier-1 path sets it
}
```

---

### `api/services/workspaceService.py` (MODIFY — service, create saga threading)

**Analog:** `_reserve_vmid_and_row` `base` dict (`api/services/workspaceService.py:280-294`).
The reservation row is built from `payload.*` then INSERTed. Thread `payload.persistent` into
`base` so the reserved row carries it (the only saga edit; stop/start already preserves the row):
```python
base = {
    "name": payload.name,
    "node": node,
    "project_repo": payload.project_repo,
    "project_branch": payload.project_branch,
    "plugin_set": payload.plugin_set,
    "status": "creating",
    "persistent": payload.persistent,   # ← add (WSX-02); flows into createWorkspace INSERT
}
```
The create route (`api/routers/workspaces.py:26-33`) needs NO change — it already passes the
whole `WorkspaceCreate` payload into `service.createWorkspace(payload)`, and `persistent` is
now a field on that DTO.

---

### `api/services/reconciler.py` (MODIFY — comment only; logic already correct)

**Analog:** itself — the predicate at `api/services/reconciler.py:107-113` already keys on
ownership, never on `stopped` state. This is WSX-04's safety bound and it is ALREADY correct.

**The single bound (DO NOT add a branch)** — `api/services/reconciler.py:107-109`:
```python
for node, vmid in sorted(managed, key=lambda nv: nv[1]):
    if vmid in live_vmids or vmid not in pool:
        continue  # SAFETY BOUND: never touch a live-owned or out-of-pool CT (V4).
    await self.compute.destroyCt(node, vmid)  # idempotent, correct node
```
`live_vmids` is computed from `db.listWorkspaces()` (`reconciler.py:97-98`), and
`SqliteProvider.listWorkspaces` filters `WHERE deletedAt IS NULL` (`sqliteProvider.py:192`) —
so a stopped persistent workspace keeps a live row → its vmid is in `live_vmids` → spared; a
soft-deleted persistent workspace drops out of the list → vmid leaves `live_vmids` → becomes
orphan-eligible. Both fall out of the EXISTING bound with zero new code.

**Phase 10 deliverable = a carve-out comment ONLY**, added at the `continue` line (~:109),
making the intent explicit: persistence protects stop→start via the live-row bound; explicit
delete intentionally removes that protection. RESEARCH anti-pattern: NEVER add a
`status == "stopped"` or `persistent` branch — that is the exact regression the negative-control
test guards (Pitfall 1). CONTEXT: keep the single safety bound in one loop.

---

### `api/tests/integration/mock_proxmox.py` (NEW — the hard gate; factory module)

**Analog:** `api/tests/integration/test_proxmox_provider.py` — same `responses` substrate
(proxmoxer rides `requests`; mock with `responses`, NEVER `respx` — Pitfall 3/5). The base
URL, UPID shape, and task-status registration are all established there.

**`responses` base + UPID shape** (`test_proxmox_provider.py:32-44, 282-283`) — the UPID MUST
be exactly 9 colon-separated segments starting `UPID:` (verified in
`api/.venv/Lib/site-packages/proxmoxer/tools/tasks.py:53-55`: `decode_upid` raises
`AssertionError("UPID is not in the correct format")` otherwise):
```python
_HOST = "pve1.local"
_BASE = f"https://{_HOST}:8006/api2/json"          # proxmoxer URL base
_NODE = "pve1"
# 9 segments: UPID:node:pid:pstart:starttime:type:id:user:comment(empty ok)
_CLONE_UPID = f"UPID:{_NODE}:0000ABCD:00100000:64000000:vzclone:201:burrow@pve:"
```

**UPID task-poll registration** — `Tasks.blocking_status`
(`proxmoxer/tools/tasks.py:31-41`) decodes the node from the UPID and polls
`prox.nodes(node).tasks(task_id).status.get()` until `data["status"] == "stopped"`.
`responses` replays registered responses in order, so N `running` then one `stopped` models a
real async task completing after a few polls (analog
`test_proxmox_provider.py:100-105` registers the status GET; `:302-313` shows the
stop-UPID running→OK pattern). Factory:
```python
import responses
from proxmoxer.core import ResourceException

def make_upid(node: str, vmid: int, ttype: str) -> str:
    """A real-shaped 9-segment UPID (decode_upid asserts exactly 9 ':' fields)."""
    return f"UPID:{node}:0000ABCD:00100000:64000000:{ttype}:{vmid}:burrow@pve:"

def register_task_poll(host, node, upid, *, exitstatus="OK", running_polls=1) -> None:
    base = f"https://{host}:8006/api2/json"
    url = f"{base}/nodes/{node}/tasks/{upid}/status"
    for _ in range(running_polls):
        responses.add(responses.GET, url,
                      json={"data": {"status": "running", "upid": upid}}, status=200)
    responses.add(responses.GET, url,
                  json={"data": {"status": "stopped", "exitstatus": exitstatus, "upid": upid}},
                  status=200)
```
> proxmoxer unwraps the `data` envelope: the status GET's `data` is the dict `_block`
> inspects (`status` + `exitstatus`), exactly as the analog registers it.

**ResourceException factory** — constructor verified in
`api/.venv/Lib/site-packages/proxmoxer/core.py:57`
(`ResourceException(status_code, status_message, content, errors=None, exit_code=None)`).
The real provider's defensive inspectors `_is_not_found` / `_is_running_or_locked`
(`api/compute/proxmoxProvider.py:337-367`) key on `status_code` and message text — produce
shapes that hit those branches:
```python
def resource_exception(status_code, message, content="") -> ResourceException:
    # status_code + message text are what _is_not_found / _is_running_or_locked read.
    return ResourceException(status_code, message, content)
```
A 404-shaped one drives the idempotent-destroy path; a 500 "CT is running" drives the
stop-then-destroy retry — mirroring the live `responses` payloads at
`test_proxmox_provider.py:294-300` (`status=500`, `"CT 201 is running"`) and `:343-348`
(`status=404`, `"CT 201 does not exist"`).

**Module shape (Claude's discretion):** factories only; promote to a shared pytest fixture
only when a second consumer appears (YAGNI — CONTEXT).

---

### `api/tests/integration/test_mock_proxmox.py` (NEW — self-tests, the gate proof)

**Analog:** `test_proxmox_provider.py::test_destroy_running_ct_stops_then_destroys`
(`api/tests/integration/test_proxmox_provider.py:286-337`) — the full stop→destroy round-trip
over `@responses.activate`, asserting `task.status == "ok"` / `exitstatus == "OK"` and the
call sequence via `responses.calls`.

**Test skeleton** (`@responses.activate` + the `_Settings` stub at
`test_proxmox_provider.py:47-73` carries only the keys the provider reads):
```python
@responses.activate
async def test_real_provider_start_blocks_on_upid_to_running() -> None:
    host, node, vmid = "pve1.local", "pve1", 201
    upid = make_upid(node, vmid, "vzstart")
    base = f"https://{host}:8006/api2/json"
    responses.add(responses.POST, f"{base}/nodes/{node}/lxc/{vmid}/status/start",
                  json={"data": upid}, status=200)
    register_task_poll(host, node, upid, exitstatus="OK", running_polls=2)  # REAL polling

    task = await _provider(host).startCt(node, vmid)   # real ProxmoxComputeProvider
    assert task.status == "ok" and task.exitstatus == "OK" and task.upid == upid
```
This must exercise the REAL `ProxmoxComputeProvider.startCt`/`stopCt`/`destroyCt`
(`api/compute/proxmoxProvider.py:241-282`) → `_block` UPID polling (`:67-96`) +
`ResourceException` branches the Fake (`ComputeTask(upid=None, status="ok")` instantly)
never triggers. That gap-closure IS the deliverable (TEST-01 / SC4).

---

### `api/tests/unit/test_reconciler.py` (MODIFY — add 2 negative-control tests)

**Analog:** `test_reconciler.py::test_reap_spares_in_pool_ct_with_a_live_row`
(`api/tests/unit/test_reconciler.py:132-142`) — already proves a live-owned in-pool CT is
spared. Reuse its exact fixtures + helpers: `compute`/`db` fixtures
(`test_reconciler.py:50-59`), `_reconciler(compute, db, now=...)` (`:66-77`),
`real_settings.worker_pool_start` for in-pool VMIDs, and `_FakeContainer` from
`compute.fakeProvider`. The container-injection idiom is `:120`
(`compute._containers[vmid] = _FakeContainer(vmid=vmid, name=..., node="pve1")`).

**Test A — persistent stopped is NEVER reaped (RED-if-regressed, SC3):**
```python
async def test_persistent_stopped_workspace_is_never_reaped(compute, db) -> None:
    vmid = real_settings.worker_pool_start + 20
    ws = await db.createWorkspace({
        "name": "persistent-stopped", "node": "pve1",
        "project_repo": "git@example.com:acme/x.git",
        "vmid": vmid, "status": "stopped", "persistent": True,
    })
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="persistent-stopped",
                                               node="pve1", running=False)
    await _reconciler(compute, db, now=datetime.now(timezone.utc)).reconcile_once()
    assert vmid in compute._containers          # survives the reap
    row = await db.getWorkspace(ws.id)
    assert row is not None and row.status == "stopped" and row.persistent is True
```

**Test B — soft-deleted persistent BECOMES orphan-eligible (CONTEXT-locked):** uses
`db.softDeleteWorkspace(ws.id)` (`sqliteProvider.py:240-249`) so the row leaves
`listWorkspaces()` → vmid leaves `live_vmids` → the CT is reclaimed:
```python
async def test_soft_deleted_persistent_workspace_becomes_orphan_eligible(compute, db) -> None:
    vmid = real_settings.worker_pool_start + 21
    ws = await db.createWorkspace({..., "vmid": vmid, "status": "stopped", "persistent": True})
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="persistent-deleted", node="pve1")
    await db.softDeleteWorkspace(ws.id)         # explicit teardown drops protection
    await _reconciler(compute, db, now=datetime.now(timezone.utc)).reconcile_once()
    assert vmid not in compute._containers      # reclaimable
```
> The two existing helpers `_running_row`/`_creating_row` (`:86-111`) build rows without
> `persistent`; these tests call `db.createWorkspace` directly to pass `status` + `persistent`,
> the same direct-create idiom used at `:194-202` (`owned_ws`).

---

### `api/tests/integration/test_workspaces_api.py` (MODIFY — persistent round-trip)

**Analog:** `_CREATE_BODY` + `_create` helper (`test_workspaces_api.py:13-34`) and
`test_stop_then_start_round_trip` (`:78-89`). Bodies are camelCase JSON over the real app.

**Create round-trip (camelCase out):** extend with a `persistent` override and assert the
camelCase key round-trips (the create POST default body has NO `persistent`, so the default
path must still return `persistent: false`):
```python
async def test_persistent_create_round_trips_camelcase(integration_client) -> None:
    data = await _create(integration_client, persistent=True)   # body uses camelCase "persistent"
    assert data["persistent"] is True

async def test_default_create_is_ephemeral(integration_client) -> None:
    data = await _create(integration_client)                    # _CREATE_BODY has no persistent
    assert data["persistent"] is False
```
> `_create(**overrides)` merges into `_CREATE_BODY` (`:28-29`); pass `persistent=True`.
> The body key is `"persistent"` (single word = identical camelCase).

**Stop→start preserves persistent:** extend `test_stop_then_start_round_trip` (`:78-89`) — a
persistent workspace returns to `running` with the SAME id/vmid and `persistent` still true:
```python
# inside a persistent variant of the round-trip:
assert started.json()["data"]["persistent"] is True
assert started.json()["data"]["vmid"] == created["vmid"]   # same VMID reused (Tier-1)
```

---

### `ui/tests/e2e/stop-start.spec.ts` (MODIFY — W2 asserted DELETE + W3 two-affordance)

**Analog:** itself — the `afterEach` (`ui/tests/e2e/stop-start.spec.ts:86-94`) and the
round-trip placeholder block (`:131-149`). W1 (id tracking via `createdIds`,
`workspaceIdByName`) already holds.

**W2 — assert the cleanup DELETE succeeded** (the current `afterEach` at `:86-94` fires the
DELETE fire-and-forget). Capture the response and assert it; 200 (deleted) or 404 (already
terminated through the UI) is acceptable (Pitfall 6):
```typescript
test.afterEach(async ({ request }) => {
  while (createdIds.length > 0) {
    const id = createdIds.pop();
    if (!id) continue;
    const res = await request.delete(`/api/v1/workspaces/${id}`);
    expect([200, 404]).toContain(res.status());   // W2: no silent cleanup failure
  }
});
```

**W3 — assert BOTH Start affordances after Stop.** The two affordances are verified in
`ui/src/components/TerminalPanel.tsx`: the header Start button
(`TerminalPanel.tsx:373-384`, `aria-label="Start workspace"`) and the placeholder CTA inside
the `role="status"` "Workspace stopped" region (`TerminalPanel.tsx:461-476`, also
`aria-label="Start workspace"`). The round-trip test (`stop-start.spec.ts:131-149`) already
scopes the click to the placeholder via `panel.getByRole("status").filter({ hasText: "Workspace stopped" })`.
Add the two-affordance assertion AFTER "Workspace stopped" is visible (`:122-124`) and BEFORE
the placeholder click:
```typescript
// W3 — after Stop, BOTH Start affordances exist (header icon + placeholder CTA).
const startButtons = panel.getByRole("button", { name: "Start workspace" });
await expect(startButtons).toHaveCount(2);   // header (TerminalPanel.tsx:376) + CTA (:463)
const placeholder = panel.getByRole("status").filter({ hasText: "Workspace stopped" });
await expect(placeholder.getByRole("button", { name: "Start workspace" })).toBeVisible();
```
> Strict mode rejects a bare two-match click — that is why the analog scopes the click to the
> placeholder region (`:136-138`). Keep that scoping; the count assertion is the only addition.
> Names are unique-per-run via `stamp` (`:23-28`), so the suite stays order-independent.

---

### `docs/adr/ADR-0011-*.md` + `docs/adr/ADR-0013-*.md` (NEW — ADR docs)

**Analog:** `docs/adr/ADR-0010-in-process-reconciler-and-capacity-lock.md` (full format).
Existing ADRs are `ADR-0001`..`ADR-0010`; the next free numbers are 0011 and 0013 (0012 is
reserved by the milestone for another phase per the file list).

**ADR skeleton** — copy the header + section structure from `ADR-0010:1-12, 56-117`:
```markdown
<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-00XX: <title>

## Status

Accepted

## Context
...
## Decision
...
## Consequences
...
## Revisit trigger
...
```
- **ADR-0013 (persistence model):** Tier-1 persistence = plain `pct stop`/`pct start` reuse of
  the same VMID, disk preserved, NO snapshot/CRIU (deferred v1.4+). Records the `persistent`
  flag + create-time-only scope.
- **ADR-0011 (setup-state store):** the `settings` singleton carrying `setupCompletedAt`,
  shared with Phase 12, behind the DbProvider seam. Records the table-shape decision
  (singleton-column vs key/value — RESEARCH A1 recommends singleton-column).
> CLAUDE.md: ADRs live in `docs/adr/`; no em dashes / no horizontal-rule lines in the body
> (the analog uses `##` section headers, not `---` dividers).

## Shared Patterns

### snake_case (Python) ↔ camelCase (JSON) ↔ camelCase (SQL column)
**Source:** `api/models/base.py:19-26` (`CamelModel`) + `api/db/sqliteProvider.py:35-42`
(`_WORKSPACE_COLUMNS` `AS` aliasing).
**Apply to:** `workspace.py` model field, the `sqliteProvider` 3 call sites, the API round-trip
test. `persistent` is single-word → camel alias is identity (no `AS` needed, unlike `lxc_ip`).
```python
# base.py: alias_generator=to_camel, populate_by_name=True, from_attributes=True
# SELECT: camelCase column AS snake_case field; serialize boundary: model_dump(by_alias=True)
```

### Migration through the `schema_migrations` ledger (the ONLY schema mechanism)
**Source:** `api/db/sqliteProvider.py:87-114` (`migrate()`).
**Apply to:** `003_persistent_and_settings.sql`.
```python
# globs *.sql sorted → records each stem in schema_migrations → applies unseen via
# conn.executescript(). Idempotent, re-runnable. DROP the file; change NOTHING in migrate().
```

### `responses` (not `respx`) for the proxmoxer HTTP leg
**Source:** `api/tests/integration/test_proxmox_provider.py:28-44` (imports + `_BASE`/UPID) and
the module docstring (`:3-10`: proxmoxer rides `requests`).
**Apply to:** `mock_proxmox.py` + `test_mock_proxmox.py`.
```python
import responses                         # NOT respx — respx patches httpx only (Pitfall 3/5)
from proxmoxer.core import ResourceException
_BASE = f"https://{host}:8006/api2/json"
@responses.activate  # on every test that registers responses.add(...)
```
> `respx` (`conftest.py:53-58`) is for the httpx ttyd-health leg ONLY; never the proxmoxer leg.

### Pure single-pass reconciler test (injected `now`, Fake compute, real temp SQLite)
**Source:** `api/tests/unit/test_reconciler.py:50-77` (fixtures + `_reconciler`) and the
`compute._containers[vmid] = _FakeContainer(...)` injection idiom (`:120`).
**Apply to:** the two WSX-04 negative-control tests.
```python
# db fixture = real SqliteProvider over tmp_path (migrated); compute = FakeComputeProvider
# _reconciler(compute, db, now=lambda: now) → reconcile_once(); assert on compute._containers
```

### SPDX header on every source file (CLAUDE.md, CONTRIBUTING.md)
**Source:** every file read this session (e.g. `api/db/migrations/001_init.sql:1-2` `-- ` form;
`api/models/workspace.py:1-2` `# ` form; `ui/tests/e2e/stop-start.spec.ts:1-2` `// ` form;
`docs/adr/ADR-0010:1-4` `<!-- -->` form).
**Apply to:** ALL new files (`003_*.sql`, `mock_proxmox.py`, `test_mock_proxmox.py`, both ADRs)
in the comment syntax for the language.

## No Analog Found

None. Every file in this phase has a direct in-repo analog. This phase is "extend in place +
lock with a test," not "add a new component" — the highest-leverage risk (per RESEARCH) is
*rebuilding* the reaper bound or the migration ledger and creating a second source of truth.

## Metadata

**Analog search scope:** `api/db/`, `api/db/migrations/`, `api/models/`, `api/services/`,
`api/compute/`, `api/routers/`, `api/tests/integration/`, `api/tests/unit/`, `ui/tests/e2e/`,
`ui/src/components/`, `docs/adr/`, and the installed `api/.venv/.../proxmoxer/` source.
**Files scanned/read:** 15 source/test files + 2 installed proxmoxer modules
(`tools/tasks.py`, `core.py`) for mock-shape verification.
**Project skills:** none found (`.claude/skills/` and `.agents/skills/` absent).
**Pattern extraction date:** 2026-06-25
