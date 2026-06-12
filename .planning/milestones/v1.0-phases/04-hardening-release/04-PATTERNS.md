<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 4: Hardening & Release - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 14 (5 backend, 6 frontend, 3 supply-chain)
**Analogs found:** 11 / 14 (3 supply-chain files have no in-repo analog)

All cited line numbers are real, verified by direct read of the current `main` tree.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/services/reconciler.py` (NEW) | service | batch / event-driven | `api/services/workspaceService.py` | role-match (saga → reconcile pass) |
| `api/main.py` (EDIT: add `lifespan`) | config / app-factory | event-driven | `api/main.py::create_app` (no lifespan exists yet) | self (extend) |
| `api/services/workspaceService.py` (EDIT: create-lock + `stopWorkspace(reason=)`) | service | CRUD / saga | itself (`createWorkspace`, `stopWorkspace`) | self (in-place edit) |
| `api/config.py` (EDIT: 3 new Settings keys) | config | — | `api/config.py` (existing `Settings` fields) | self (extend) |
| `api/tests/unit/test_reconciler.py` (NEW) | test | batch | `api/tests/unit/test_compensation.py` + `test_create_saga.py` | exact (Fake + temp SQLite) |
| `api/tests/integration/test_capacity_race.py` (NEW) | test | request-response | `api/tests/unit/test_create_saga.py` (`_LockOnceDb`, gather) | role-match |
| `ui/src/components/ActivityDrawer.tsx` (NEW) | component | request-response (poll) | `WorkspaceList.tsx` (shimmer/poll-error) + `NewWorkspaceModal.tsx` (dialog/Esc/trap) + `TerminalPanel.tsx` (icon buttons) | role-match (composite) |
| `ui/src/hooks/useWorkspaceEvents.ts` (NEW) | hook | request-response (poll) | `ui/src/hooks/useWorkspaces.ts` | exact |
| `ui/src/lib/events.ts` (NEW: `EVENT_BADGE`) | utility | transform | `ui/src/lib/status.ts` (`STATUS_COLOR`) | exact |
| `ui/src/types/event.ts` (NEW) or extend `workspace.ts` | model | — | `ui/src/types/workspace.ts` | exact |
| `ui/src/components/TerminalPanel.tsx` (EDIT: activity trigger) | component | — | itself (icon-button cluster) | self (in-place edit) |
| `ui/src/components/ActivityDrawer.test.tsx` (NEW) | test | — | `WorkspaceList.test.tsx` + `NewWorkspaceModal.test.tsx` | exact (vitest + MSW) |
| `ui/tests/e2e/activity-drawer.spec.ts` (NEW) | test | — | `ui/tests/e2e/terminal.spec.ts` | exact (Playwright + Fake) |
| `Dockerfile.api`, `Dockerfile.ui`, `.dockerignore` (NEW) | config | file-I/O | **NONE** (see No Analog Found) | none |
| `.github/workflows/ci.yml` (EDIT: build+scan job) | config | — | `.github/workflows/ci.yml::static-gates` job | self (extend DAG) |
| `.github/workflows/release.yml` (NEW) | config | — | `.github/workflows/ci.yml` (SHA-pin + per-job perms convention) | partial (convention only) |

## Pattern Assignments

### `api/services/reconciler.py` (service, batch / event-driven) — NEW

**Analog:** `api/services/workspaceService.py`

The reconciler is a *new* service that reuses the same seams `WorkspaceService` depends on (the two provider ABCs + `Settings`) and the same `_safe()` redactor. Copy the constructor/seam-discipline shape and the compensation/idempotent-destroy primitives; do NOT copy the per-workspace lock (the reconciler is a single periodic pass, not a per-id mutation).

**Seam-discipline header + constructor** (`workspaceService.py:12-17`, `81-99`) — mirror this exactly; the reconciler imports ONLY `ComputeProvider`, `DbProvider`, `Settings`, never `aiosqlite`/`proxmoxer`:
```python
from compute.provider import ComputeProvider
from db.provider import DbProvider, VmidTakenError
from config import Settings
# Seam discipline (CLAUDE.md): depends ONLY on the two provider ABCs + Settings.
# No aiosqlite, no proxmoxer — the seam-leakage guard enforces this.
```
Add the **injectable `now`** the research mandates (NOT present in `WorkspaceService`, which uses the static `_now()` at `workspaceService.py:352-355`): `def __init__(self, compute, db, settings, now=None): self._now = now or (lambda: datetime.now(timezone.utc))`.

**Idempotent compensation primitive to reuse** (`workspaceService.py:200-216`) — the reaper's orphan destroy is exactly this stop-then-destroy, tolerant of absence:
```python
async def _compensate(self, node: str, vmid: int) -> None:
    try:
        await self.compute.stopCt(node, vmid)
    except Exception:
        pass  # best-effort: a not-running CT cannot be stopped
    try:
        await self.compute.destroyCt(node, vmid)
    except Exception:
        pass  # best-effort: destroy of a missing CT is a no-op
```
`destroyCt` is idempotent in BOTH providers (Fake: `fakeProvider.py:146-156`, stops-then-pops, no-op on missing) — the reaper needs no new compute method.

**`usedVmids()` ∩ pool-range minus live DB rows** — the set-difference primitives:
- `compute.usedVmids()` is the abstract method (`provider.py:77-86`); the Fake returns ALL containers unfiltered (`fakeProvider.py:105-107`: `return set(self._containers.keys())`), so the reaper MUST re-assert `if vmid in pool` itself (Pattern 2 safety bound / RESEARCH A4).
- live DB VMIDs — copy `_db_used_vmids` verbatim (`workspaceService.py:195-198`):
```python
async def _db_used_vmids(self) -> set[int]:
    rows = await self.db.listWorkspaces()
    return {row.vmid for row in rows if row.vmid is not None}
```

**`_safe()` redactor to reuse** — already exported (`workspaceService.py:427`: `__all__ = ["WorkspaceService", "_safe"]`). Import `from services.workspaceService import _safe` for `reaper.*` event/log text. It strips git/CI tokens, URL userinfo, long opaque tokens, caps at 200 chars (`workspaceService.py:66-78`). Do NOT hand-roll a new scrubber.

**Idle detection — `getEvents` ordering** (`db/provider.py:77-80`): `getEvents(workspaceId)` returns **oldest-first** (WS-11). The idle check keys on the LAST terminal event being a `terminal.disconnected`. The two terminal event types are written by `routers/terminal.py:114` (`terminal.connected`) and `:145` (`terminal.disconnected`), both with `{}` data. `listWorkspaces(status="running")` is the input set (`db/provider.py:57-59`).

**Auto-stop must call the guarded transition, not raw `stopCt`** — reuse `WorkspaceService.stopWorkspace` (`workspaceService.py:219-234`), which honors `assert_transition`, the per-workspace lock, and `stoppedAt`. See the `stopWorkspace(reason=)` edit below for threading `reason: idle`.

---

### `api/main.py` (config / app-factory, event-driven) — EDIT: add `lifespan`

**Analog:** `api/main.py::create_app` itself (`main.py:155-199`) — **there is no lifespan today**; `create_app` builds `FastAPI(title=..., version=...)` at `main.py:168` with no `lifespan=`. This is the attach point.

**App-construction line to extend** (`main.py:168`):
```python
app = FastAPI(title="Burrow Control Plane", version="0.1.0")
```
becomes `FastAPI(title=..., version="0.1.0", lifespan=lifespan)`.

**Provider-wiring pattern to reuse for `build_reconciler()`** — the lifespan must build the reconciler from the SAME seams the DI uses. Copy the singleton/branch pattern from `get_compute` (`main.py:79-94`) and `get_db` (`main.py:108-114`). Critically, the Fake is a **process-wide singleton** (`main.py:70-75`, `_compute_singleton`) so the reconciler MUST receive the same instance the request path uses, or the reaper sees a different (empty) Fake. Pull the reconciler's compute from `get_compute()` and db from `get_db()`.

**Lifespan shape to add** (no in-repo precedent; RESEARCH Pattern 1 is the source) — broad `except` around each pass, clean `cancel()` + `suppress(CancelledError)` on shutdown:
```python
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconciler = Reconciler(get_compute(), get_db(), settings)
    task = asyncio.create_task(_reconcile_loop(reconciler, settings.reconciler_period_s))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
```

---

### `api/services/workspaceService.py` (service, CRUD / saga) — EDIT: capacity-lock + `stopWorkspace(reason=)`

**Analog:** the file itself.

**Capacity-race fix** — wrap the existing step-0 guard (`workspaceService.py:111-113`) and step-1 reservation (`:116`) in ONE `asyncio.Lock`. The lock pattern already exists in this file (`_locks` dict at `:99`, `_lock_for` at `:337-343`) — add a single process-wide `self._create_lock = asyncio.Lock()` in `__init__` (`:84-99`). Today these two steps are unserialized:
```python
# 0 — capacity guard (CAP-01); node is operator-selected (CAP-04).
if await self.compute.getNodeMemory(payload.node) > self.settings.capacity_threshold:
    raise CapacityError(payload.node)
# 1 — reserve VMID via the DB partial-unique INSERT (the race arbiter).
ws = await self._reserve_vmid_and_row(payload)
```
Wrap BOTH in `async with self._create_lock:` so two creates cannot both pass a stale capacity read (Pitfall 5). The VMID INSERT is already cross-process race-safe via `VmidTakenError` retry (`:180-193`); only the capacity READ is the gap. The lock must span ONLY check+reserve, releasing before the multi-second clone (RESEARCH "Atomic capacity-check+reserve" example).

**`stopWorkspace(reason=)` thread** — the current method (`workspaceService.py:219-234`) logs `workspace.stopped` with `{}` at `:233`:
```python
await self.db.logEvent(ws.id, "workspace.stopped", {})
```
Add `*, reason: str | None = None` to the signature and emit `{"reason": reason}` when set, so the reconciler's auto-stop carries `reason: "idle"` into the event `data` (the UI badge keys on `data.reason === "idle"` — see `events.ts` below). Operator-initiated stops pass no reason → `{}` → label "Stopped" (Open Q2 / RESEARCH A3).

---

### `api/config.py` (config) — EDIT: 3 new Settings keys

**Analog:** the existing `Settings` fields, especially the "Saga timeouts (seconds)" block (`config.py:61-65`):
```python
ttyd_timeout: float = 60  # saga step 6: total ttyd-health wait
ttyd_interval: float = 2  # saga step 6: poll interval
clone_timeout: float = 300  # UPID wait for a --full clone
```
Add, in the same style (non-secret, safe defaults within CONTEXT ranges): `reconciler_period_s: float = 60`, `creating_timeout_s: float = 300`, `idle_window_s: float = 1800`. The worker-pool range the reaper bounds against already exists (`config.py:46-47`: `worker_pool_start: int = 200`, `worker_pool_end: int = 299`) and `default_node` (`:48`) for row-less orphan destroy (RESEARCH A7).

---

### `api/tests/unit/test_reconciler.py` (test, batch) — NEW

**Analog:** `api/tests/unit/test_compensation.py` + `api/tests/unit/test_create_saga.py`

**Fixture pattern to copy** (`test_compensation.py:37-47` / `test_create_saga.py:29-45`) — temp SQLite + clean Fake, no real clock:
```python
@dataclass
class _DbSettings:
    database_path: str

@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "recon.db")))
    await provider.migrate()
    return provider
```

**Orphan + stale-creating injection** (RESEARCH `04-RESEARCH.md:554-561`) — inject directly into the Fake's `_containers` (a real, shipped attribute, `fakeProvider.py:72`) and create a stale `creating` row, then drive ONE pass with an injected `now`:
```python
fake_compute._containers[250] = _FakeContainer(vmid=250, name="orphan", node="pve1")  # no DB row
stale = await sqlite_db.createWorkspace(_ws_data("stuck", 251, status="creating"))
recon = Reconciler(fake_compute, sqlite_db, settings,
                   now=lambda: _parse(stale.created_at) + timedelta(seconds=999))
await recon.reconcile_once()
assert 250 not in fake_compute._containers           # orphan reaped
assert (await sqlite_db.getWorkspace(stale.id)).status == "error"
```

**Event-assertion pattern** (`test_create_saga.py:83-88`, `test_compensation.py:74-76`) — read `getEvents` and filter by type:
```python
events = await db.getEvents(ws.id)
assert any(e.type == "reaper.timed_out" for e in events)
```
The negative tests (fresh `creating` NOT swept — Pitfall 1; reconnect-within-window NOT stopped — Pitfall 2) follow the same single-pass shape with a different injected `now`.

**Redaction regression** — mirror `test_compensation.py:115-139` (`test_boot_error_event_carries_no_secret`): assert a secret-shaped token never appears in a `reaper.*` event's `data`.

---

### `api/tests/integration/test_capacity_race.py` (test, request-response) — NEW

**Analog:** `api/tests/unit/test_create_saga.py` (the `_LockOnceDb` subclass at `:138-165` + the service fixture).

**Concurrency driver** (RESEARCH `04-RESEARCH.md:531-547`) — `asyncio.gather` two creates against a Fake whose `getNodeMemory` flips above threshold once one workspace exists:
```python
results = await asyncio.gather(
    service.createWorkspace(payload_a),
    service.createWorkspace(payload_b),
    return_exceptions=True,
)
successes = [r for r in results if not isinstance(r, Exception)]
capacity_errors = [r for r in results if isinstance(r, CapacityError)]
assert len(successes) == 1 and len(capacity_errors) == 1
```

**Fake subclass for the flipping memory** — mirror the `_LockOnceDb`/`_LogEventFailingDb` subclassing technique (`test_create_saga.py:138-165`, `test_compensation.py:155-169`): subclass `FakeComputeProvider` and override `getNodeMemory` (`fakeProvider.py:180-182`) to return a value computed from `len(self._containers)`. WITHOUT the lock both creates pass; WITH it, exactly one does (proves the fix bites). The ttyd-stub pattern (`test_create_saga.py:55-59`, monkeypatch `_wait_ttyd`) keeps it network-free.

---

### `ui/src/hooks/useWorkspaceEvents.ts` (hook, poll) — NEW

**Analog:** `ui/src/hooks/useWorkspaces.ts`

**Hook to mirror** (`useWorkspaces.ts:18-28`) — same `api<T>` call, same `refetchInterval: 3000`, but add the `enabled` gate so polling only runs while the drawer is open:
```typescript
const POLL_INTERVAL_MS = 3000;  // match the workspace-list cadence

export function useWorkspaceEvents(id: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["workspace-events", id],
    queryFn: () => api<WorkspaceEvent[]>(`/workspaces/${id}/events`),
    refetchInterval: POLL_INTERVAL_MS,
    enabled: enabled && !!id,   // 04-UI-SPEC criterion 5: poll ONLY while open
  });
}
```
The `api<T>` wrapper (`api/client.ts:26-36`) unwraps the `{data,meta,error}` envelope and throws `ApiError` on a non-null `error` — reuse as-is. The endpoint is `GET /api/v1/workspaces/{id}/events` (`routers/workspaces.py:88-98`), which returns events **oldest-first**, so the component reverses client-side.

---

### `ui/src/lib/events.ts` (utility, transform) — NEW: `EVENT_BADGE`

**Analog:** `ui/src/lib/status.ts`

**Record pattern to mirror** (`status.ts:14-20`) — tokens only, no hex, single source of truth:
```typescript
export const STATUS_COLOR: Record<WorkspaceStatus, string> = {
  running: "var(--ok)",
  creating: "var(--warn)",
  ...
};
```
The new `EVENT_BADGE` keys off the **real namespaced backend strings** (04-UI-SPEC §"Event type → badge color map" is the binding table; `04-RESEARCH.md:568-579` has the literal map). Verified backend types: `workspace.created`/`started`/`stopped`/`destroyed` (`workspaceService.py:144,233,251,271`), `bootconfig.persisted` (`:389`), `boot.error` (`:159`), `terminal.connected`/`disconnected` (`terminal.py:114,145`), and Phase-4's new `reaper.*`. Include the `reaper.*` prefix match (`--warn`) and an unknown→raw-mono fallback (forward-compatible, criterion 3). `workspace.stopped` special-cases `data.reason === "idle"` → label "Auto-stopped (idle)", dot `--warn`.

---

### `ui/src/types/event.ts` (model) — NEW (or extend `workspace.ts`)

**Analog:** `ui/src/types/workspace.ts`

**camelCase-mirrors-backend convention** (`workspace.ts:4-31` header + `Workspace` interface) — the JSON is camelCase via `model_dump(by_alias=True)`. The `WorkspaceEvent` TS type mirrors `api/models/event.py:16-24` (`id`, `workspace_id`→`workspaceId`, `type`, `data`, `created_at`→`createdAt`):
```typescript
export interface WorkspaceEvent {
  id: string;
  workspaceId: string;
  type: string;
  data: Record<string, unknown>;
  createdAt: string;
}
```
The `ApiEnvelope<T>` type (`workspace.ts:51-55`) is already exported for the `api<T>` call.

---

### `ui/src/components/ActivityDrawer.tsx` (component, poll) — NEW

**Analog (composite):** `WorkspaceList.tsx` (shimmer + poll-error), `NewWorkspaceModal.tsx` (dialog/Esc/focus-trap/scrim), `TerminalPanel.tsx` (icon buttons + inline SVG).

**ShimmerRows — copy verbatim** (`WorkspaceList.tsx:184-203`):
```typescript
function ShimmerRows() {
  return (
    <ul style={listStyle} aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <li key={i} style={{ height: "44px", margin: "0 0 2px",
            borderRadius: "var(--radius-control)", background: "var(--bg-hover)",
            animation: "pulse 1.4s ease-in-out infinite", opacity: 0.5 }} />
      ))}
    </ul>
  );
}
```

**Poll-error strip — copy the `role="alert"` + `borderLeft 2px solid --err` pattern** (`WorkspaceList.tsx:264-279`). 04-UI-SPEC reuses this exact treatment for the drawer error state AND the `boot.error` row emphasis:
```typescript
<div role="alert" style={{ ...,
    background: "var(--bg-panel-alt)",
    borderLeft: "2px solid var(--err)",
    color: "var(--err)", fontSize: "11.5px" }}>
  {POLL_ERROR}
</div>
```

**Dialog + Esc + focus-on-mount + scrim — mirror `NewWorkspaceModal`** (`NewWorkspaceModal.tsx:283-321`): the `role="dialog"` + `aria-label` + `tabIndex={-1}` + `onKeyDown` Esc handler + `dialogRef.current?.focus()` on mount (`:217-220`) + the `<button>` scrim for keyboard-accessible click-dismiss (`:297-312`). 04-UI-SPEC additionally requires focus RETURN to the trigger on close (NewWorkspaceModal does not do this — add a small `useEffect`).
```typescript
const onKeyDown = (e: React.KeyboardEvent) => {
  if (e.key === "Escape") { onClose(); return; }
};
```

**Icon button + inline SVG — reuse `iconButtonStyle` + `CloseIcon`** (`TerminalPanel.tsx:120-130` for the 24px button, `:94-107` for the `×` close glyph). The new activity-trigger glyph is a 1.5px-stroke inline SVG following the `ICON` spread convention (`TerminalPanel.tsx:36-42`), placed LEFT of `split` in the header cluster (`:250-278`) so the destructive `terminate` stays rightmost (04-UI-SPEC §Drawer trigger).

**Newest-first reverse** (04-UI-SPEC criterion 2): `const rows = useMemo(() => [...(data ?? [])].reverse(), [data]);` — the endpoint is oldest-first (`getEvents`, `db/provider.py:79`).

---

### `ui/src/components/TerminalPanel.tsx` (component) — EDIT: add activity trigger

**Analog:** the file itself. Add one more `<button style={iconButtonStyle}>` to the header cluster (`TerminalPanel.tsx:249-278`), LEFT of the Split button (`:250-257`), with `aria-label="Activity log"` and a new inline SVG glyph (1.5px stroke, `ICON` spread `:36-42`). On click it sets the single `activeEventsWorkspaceId` (new ephemeral client state, NOT persisted — 04-UI-SPEC §Drawer trigger) for `this` panel's `id`.

---

### `ui/src/components/ActivityDrawer.test.tsx` (test) — NEW

**Analog:** `WorkspaceList.test.tsx` + `NewWorkspaceModal.test.tsx`

**MSW + QueryClient harness — copy** (`WorkspaceList.test.tsx:26-45`): `new QueryClient({ defaultOptions: { queries: { retry: false } } })` so a forced poll error surfaces `isError` immediately, wrapped in `QueryClientProvider`. Override the events endpoint per-test with `server.use(http.get("/api/v1/workspaces/:id/events", ...))` (mirror `:112-136`).

**State-coverage tests** (mirror `WorkspaceList.test.tsx:167-192`): loading→shimmer, empty→`No activity yet`, error→`--err` strip over kept rows, populated→reversed list. **Esc-closes test** — copy `NewWorkspaceModal.test.tsx:176-183` (`fireEvent.keyDown(getByRole("dialog"), { key: "Escape" })` → `onClose` called). **Badge/reverse/emphasis** assertions key on the namespaced types and assert the most-recent event is the top row (criterion 2).

---

### `ui/tests/e2e/activity-drawer.spec.ts` (test) — NEW

**Analog:** `ui/tests/e2e/terminal.spec.ts`

**Journey harness — reuse** (`terminal.spec.ts:32-45`): the `createWorkspace(page, name)` helper (open modal → fill `#ws-name`/`#ws-repo`/`#ws-branch` → Create → wait for panel) and the `test.describe.configure({ mode: "serial" })` discipline (`:25`). The whole `playwright.config.ts` stack (Fake provider + standalone stub ttyd + `vite preview`, `playwright.config.ts:32-70`) is already wired — the drawer spec just adds: create → open the activity trigger → assert event rows render (the workspace logs `workspace.created`/`bootconfig.persisted` at birth) → close via `×`/`Esc`. No new harness needed.

## Shared Patterns

### Secret/topology redaction (`_safe`)
**Source:** `api/services/workspaceService.py:66-78` (exported at `:427`)
**Apply to:** every `reaper.*` event `data` and every reconciler structured log line (V7 / ASVS). Import it; do not re-implement.
```python
from services.workspaceService import _safe
# message = _safe(exc)  → "ExcType: <redacted, ≤200 chars>"
```

### Seam discipline (no driver imports past the ABC)
**Source:** `api/services/workspaceService.py:12-17` (prose) + enforced by `api/tests/unit/test_seam_leakage.py:35-39`
**Apply to:** `reconciler.py` — it MUST import only `ComputeProvider`/`DbProvider`/`Settings`. The tokenize guard (`test_seam_leakage.py:71-80`) fails the build if `proxmoxer`/`aiosqlite` appears as code in any non-owning file. The reaper drives `compute.destroyCt`/`usedVmids` through the ABC only.

### Idempotent destroy (no new compute method)
**Source:** `api/compute/fakeProvider.py:146-156` (Fake) + abstract contract `api/compute/provider.py:120-123`
**Apply to:** the reaper's orphan destroy and the timed-out-`creating` sweep. Destroy of a missing CT is a no-op in BOTH providers (Pitfall 7) — the reaper calls `destroyCt(node, vmid)` directly for row-less orphans (no state machine to guard) and via `_compensate`-style for stale rows.

### Standard envelope + camelCase JSON
**Source:** `api/routers/workspaces.py:33` (`respond(...model_dump(by_alias=True))`) + `ui/src/api/client.ts:26-36` (unwrap)
**Apply to:** no new route this phase (the drawer reuses the shipped events endpoint). The `WorkspaceEvent` TS type mirrors the camelCase JSON of `api/models/event.py`.

### Tokens-only color discipline (no hex, no gold in the drawer)
**Source:** `ui/src/lib/status.ts:14-20` + `WorkspaceList.tsx` (all `var(--token)`)
**Apply to:** `ActivityDrawer.tsx` + `events.ts` — every color resolves from a `--token`; accent (`--accent-line`) only as the focus ring; zero `--gold` (04-UI-SPEC criteria 1 & 7).

### SHA-pinned actions + per-job least-priv permissions
**Source:** `.github/workflows/ci.yml:9-10` (convention) + `:30,33,36,103` (pinned SHAs with trailing version comment) + `:19-21,26-27` (default `contents: read`, per-job perms)
**Apply to:** both the new `ci.yml` build+scan job and `release.yml`. Pin every new action to a full commit SHA with a `# vX.Y.Z` trailing comment, exactly as `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1` (`ci.yml:30`).

## No Analog Found

Files with no close in-repo match — the planner uses `docs/ci-cd-and-testing.md` §2.2/§5 + RESEARCH Patterns 5/6 instead:

| File | Role | Data Flow | Reason / Authoritative Source |
|------|------|-----------|-------------------------------|
| `Dockerfile.api` | config | file-I/O | No Dockerfile exists in the repo (verified: no `Dockerfile*` match). Follow ci-cd §2.2 (`ci-cd-and-testing.md:65-81`): multi-stage, base pinned `@sha256:`, non-root, read-only root FS, `HEALTHCHECK` on `GET /api/v1/health` (verified path: `routers/health.py:22` prefix `/api/v1` + `:33` `/health` — NOT `/health` as the spec snippet says; use the real mounted path), OCI labels, `uv sync --frozen`. Base `python:3.12-slim` (ci-cd §2.1, `:51`; slim not distroless per §9 Open Q1). Pitfall 8: `COPY --chown`, Python `urllib` health probe (no `curl` assumption). |
| `Dockerfile.ui` | config | file-I/O | Same — no analog. ci-cd §2.1 (`:52`): `node:22` build → `nginx:1.27-alpine` runtime; HEALTHCHECK = nginx 200 on `/`; `npm ci` from lockfile. |
| `.dockerignore` | config | — | No analog. ci-cd §2.2 (`:80-81`): exclude `.git`, `.env*`, tests, local state (keeps context secret-free; the threat model's "build context leaks .env" mitigation). |
| `.github/workflows/release.yml` | config | — | No release workflow exists (verified). Only the SHA-pin + per-job-permission *convention* transfers from `ci.yml`. The structure (build+push by digest → syft SBOM SPDX+CycloneDX → cosign keyless → `attest-build-provenance`) is RESEARCH Pattern 6 + ci-cd §5.4 (`:282-296`). Job perms: exactly `contents: read, packages: write, id-token: write, attestations: write` (Pitfall 7 / ci-cd §5.5 `:298-308`). |

> Note: the `ci.yml` build+scan **job** is an EDIT (extend the existing DAG, analog = the `static-gates` job structure), but the **Dockerfiles it builds** have no analog. The Trivy two-run gate (Pattern 5) has no in-repo precedent — it is new YAML governed by ci-cd §5.2.

## FROZEN / Reuse Guardrails (for the planner)

These are load-bearing constraints the planner MUST encode in the plans:

1. **Seam discipline is CI-enforced.** `reconciler.py` importing `aiosqlite` or `proxmoxer` fails `test_seam_leakage.py` (the tokenize guard, `test_seam_leakage.py:71-80`). The reaper goes through `ComputeProvider`/`DbProvider` ONLY — no new Proxmox/SQLite call, no `verify_ssl=False` regression (RESEARCH State-of-the-Art).

2. **Events FK requires a live `workspaceId`.** `db.logEvent` (`db/provider.py:72-75`) writes against the `events` table FK. A truly orphaned CT (leaked VMID, no row) CANNOT satisfy it → row-less reaps log STRUCTURALLY via `logger.info("reaper.destroyed", extra={...})` (redacted), NOT a DB event (Pitfall 3 / Open Q1). Timed-out `creating` rows and idle auto-stops DO have a row → normal `logEvent`. The drawer correctly never shows row-less reaps (no workspace to open).

3. **`reason: idle` must reach the event `data`.** The UI badge map keys on `data.reason === "idle"` (04-UI-SPEC §badge map, `workspace.stopped` row). Thread it via a new optional `reason` param on `stopWorkspace` (`workspaceService.py:219-234`, the `:233` `logEvent` call) — NOT a reconciler-side duplicate event (Open Q2 / RESEARCH A3).

4. **Reaper safety bound (V4 authorization-of-action).** Only ever destroy a VMID that is BOTH in `[worker_pool_start, worker_pool_end]` (`config.py:46-47`) AND absent from live DB rows. The Fake's `usedVmids()` is UNFILTERED (`fakeProvider.py:105-107`), so the `if vmid in pool` bound MUST live in the reconciler (RESEARCH A4). A test must assert an out-of-pool CT is untouched.

5. **Reconcile logic stays pure; the loop is thin.** All decisions are a function of (DB state, compute state, injected `now`) — zero `asyncio.sleep`, zero wall-clock, zero `freezegun` (RESEARCH Don't-Hand-Roll). The periodic loop the lifespan owns is tested separately and minimally (clean start/cancel, Pitfall 4).

6. **Capacity lock spans check+reserve only.** The `asyncio.Lock` wraps the step-0 guard + step-1 reservation, releasing BEFORE the multi-second clone (`workspaceService.py:120-145`), so concurrent creates still parallelize their slow work. v1 assumes `--workers 1`; the `BEGIN IMMEDIATE` cross-process path is documented but deferred (RESEARCH A1 / Open Q3).

7. **No new runtime dependency.** Zero new PyPI/npm package across the phase (RESEARCH Standard Stack). CI additions are SHA-pinned GitHub Actions in YAML, not app installs. The drawer adds no drawer/dialog library — it is hand-built on the existing tokens (04-UI-SPEC Registry Safety).

8. **SPDX header on every NEW source file** (CLAUDE.md): `reconciler.py`, `test_reconciler.py`, `test_capacity_race.py`, `ActivityDrawer.tsx`, `useWorkspaceEvents.ts`, `events.ts`, `event.ts`, both Dockerfiles, `.dockerignore`, `release.yml`, both new test specs — the two-line AGPL header in the language's comment syntax.

## Metadata

**Analog search scope:** `api/services/`, `api/compute/`, `api/db/`, `api/routers/`, `api/tests/{unit,integration,e2e}/`, `api/{main,config}.py`, `api/models/`, `ui/src/{components,hooks,lib,api,types}/`, `ui/tests/e2e/`, `.github/workflows/`, `docs/ci-cd-and-testing.md`.
**Files scanned (read in full or targeted):** ~22.
**Pattern extraction date:** 2026-06-11

## PATTERN MAPPING COMPLETE

**Phase:** 4 - Hardening & Release
**Files classified:** 16 (counting EDIT targets separately)
**Analogs found:** 11 strong in-repo analogs / 3 supply-chain files with no analog (Dockerfiles + .dockerignore + release.yml structure)

### Coverage
- Files with exact analog: 6 (`useWorkspaceEvents`←`useWorkspaces`, `events.ts`←`status.ts`, `event.ts`←`workspace.ts`, `test_reconciler.py`←`test_compensation/create_saga`, `ActivityDrawer.test.tsx`←`WorkspaceList/NewWorkspaceModal.test`, `activity-drawer.spec.ts`←`terminal.spec.ts`)
- Files with role-match / composite analog: 5 (`reconciler.py`←`workspaceService.py`, `ActivityDrawer.tsx`←WorkspaceList+NewWorkspaceModal+TerminalPanel, `test_capacity_race.py`←test_create_saga, ci.yml build-job←static-gates job, release.yml←ci.yml convention)
- Files edited in place (self-analog): `main.py`, `workspaceService.py`, `config.py`, `TerminalPanel.tsx`
- Files with no analog: 3 (`Dockerfile.api`, `Dockerfile.ui`, `.dockerignore`) — use ci-cd §2.2

### Key Patterns Identified
- The reconciler is pure assembly of EXISTING seams: `_compensate`/idempotent `destroyCt`, `_db_used_vmids`, `_safe` (exported), `getEvents` oldest-first, `stopWorkspace` guarded transition — the only NEW backend code is `Reconciler.reconcile_once()` + an injected `now` + a FastAPI `lifespan` (`main.py` has none today).
- The capacity-race fix is a one-block edit: a process `asyncio.Lock` wrapping the already-present step-0 guard + step-1 reserve (`workspaceService.py:111-116`); the lock machinery (`_locks`/`_lock_for`) already exists in the same file.
- The drawer is a composite of three shipped UI patterns — `WorkspaceList` shimmer/`role=alert` strip, `NewWorkspaceModal` dialog/Esc/focus/scrim, `TerminalPanel` `iconButtonStyle`/inline-SVG — plus a `useWorkspaces`-mirrored `enabled`-gated poll and a `status.ts`-mirrored `EVENT_BADGE` keyed on the REAL namespaced event strings.
- The supply-chain half has no in-repo file analog (no Dockerfiles/release.yml exist) but inherits the `ci.yml` SHA-pin + per-job-permission convention; the verified health path is `/api/v1/health`, not the spec's `/health`.

### File Created
`E:\repos\burrow\.planning\phases\04-hardening-release\04-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. The planner can reference each analog file + line range directly in PLAN.md action sections across the three independent slices (runtime-hardening, activity drawer, supply-chain release).
