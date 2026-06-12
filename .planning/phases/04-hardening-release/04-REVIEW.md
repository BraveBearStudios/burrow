---
phase: 04-hardening-release
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - api/services/reconciler.py
  - api/services/workspaceService.py
  - api/main.py
  - api/config.py
  - api/tests/unit/test_reconciler.py
  - api/tests/integration/test_capacity_race.py
  - api/tests/integration/test_lifespan.py
  - ui/src/components/ActivityDrawer.tsx
  - ui/src/hooks/useWorkspaceEvents.ts
  - ui/src/lib/events.ts
  - ui/src/types/event.ts
  - ui/src/components/TerminalPanel.tsx
  - ui/tests/e2e/activity-drawer.spec.ts
  - Dockerfile.api
  - Dockerfile.ui
  - .dockerignore
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - docs/adr/ADR-0010-in-process-reconciler-and-capacity-lock.md
  - ui/src/components/ActivityDrawer.test.tsx
findings:
  critical: 1
  blocker: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

The Phase-4 hardening surfaces are largely sound on the high-value axes the
brief flagged: the reaper's pool-range bound IS re-asserted inside the reconciler
(`reconciler.py:99`, not delegated to the Fake's unfiltered `usedVmids()`); the
capacity-check + VMID-reserve are serialized under `_create_lock` spanning ONLY
check+reserve, released before the slow clone (`workspaceService.py:125-130`); the
lifespan cancels the reconcile task cleanly and a failing pass survives
(`main.py:153-188`); `release.yml` carries exactly the four required publish scopes
with SHA-pinned actions, keyless cosign + SLSA + dual SBOM bound to the digest, and
no PAT; `Dockerfile.api/.ui` are multi-stage, digest-pinned, non-root, with the
API HEALTHCHECK on the verified `/api/v1/health`; `.dockerignore` excludes `.env*`,
`.git`, and `*.pem`/`*.key`; and the ActivityDrawer renders server data verbatim
with the badge map keyed off real namespaced strings and the poll gated on open.

Two real defects break the "reaper cannot leak / cannot lie" guarantee and the
"UI only ever sees redacted data" contract:

1. **The orphan reaper destroys against the wrong node** — it hardcodes
   `settings.default_node` for a CT that may live on any operator-selected node.
   On Proxmox the DELETE 404s, is swallowed as idempotent success, and the reaper
   logs `reaper.destroyed` — a silent VMID/CT leak with a false audit trail.
   (BLOCKER — this is the exact "must ONLY destroy pool-range, no-live-owner CTs"
   surface the brief calls load-bearing; it does not destroy them at all
   off-default-node, while claiming it did.)
2. **`bootconfig.persisted` event data is logged un-redacted** — `project_repo`
   and `config_repo` go straight into event `data` with no `_safe()` pass, while
   `ui/src/types/event.ts` asserts all `data` is "already server-redacted
   (`_safe()`)" and the drawer renders it verbatim. A credential-bearing repo URL
   would surface in the UI. (WARNING — the documented threat model treats
   `project_repo` as non-secret, but the redaction claim is false and the path is
   user-reachable.)

The remaining items are robustness/a11y/quality WARNINGs and INFOs.

## Critical Issues

### CR-01: Orphan reaper destroys against `default_node`, leaking off-node CTs and logging a false success

**File:** `api/services/reconciler.py:101` (and the node source at `:92`)
**Issue:**
The row-less-orphan branch (case A) destroys a pool VMID with a hardcoded node:

```python
await self.compute.destroyCt(self.settings.default_node, vmid)  # idempotent
...
logger.info("reaper.destroyed", extra={"vmid": vmid})
```

But `vmid` here comes from `compute.usedVmids()`, which on the real provider scans
`cluster.resources` **cluster-wide** (`proxmoxProvider.py:135`) — across every node,
not just `default_node`. The create payload's `node` is free-form operator input
(`models/workspace.py:42`, required, no default; CAP-04 "operator-selected node"),
so an orphan CT can live on any node. `ProxmoxComputeProvider.destroyCt` issues
`self._api.nodes(node).lxc(vmid).delete()` (`proxmoxProvider.py:238`); a DELETE
aimed at the wrong node returns 404, which `_is_not_found` treats as idempotent
success (`proxmoxProvider.py:240-241`). Result: the orphan CT on the real node is
**never destroyed and its VMID is never freed**, yet the reaper emits
`reaper.destroyed` for it — a silent fleet leak plus a misleading audit log line.

The timed-out-`creating` branch is correct by contrast: it uses `row.node`
(`reconciler.py:113`). The orphan branch has no DB row, so it must learn the real
node from the compute snapshot.

The unit test masks this because the Fake's `destroyCt` ignores `node` entirely
(`fakeProvider.py:146-156` — keyed only on `vmid`), so `test_reap_destroys_in_pool_orphan_and_spares_out_of_pool`
passes regardless of which node string is passed. CI-provable correctness over the
Fake does not cover this real-provider divergence.

**Fix:**
Extend the compute seam so the reaper learns each orphan's node, then destroy
against that node. Minimal change: have `usedVmids()` (or a sibling reader) return
`{vmid: node}` for the pool, or add a `getNode(vmid)`; then:

```python
# (A) Row-less orphans in the pool → idempotent destroy + structured log.
orphans = await self.compute.poolContainers()  # {vmid: node} over the pool
for vmid, node in sorted(orphans.items()):
    if vmid in live_vmids or vmid not in pool:
        continue  # SAFETY BOUND: never touch a live-owned or out-of-pool CT.
    await self.compute.destroyCt(node, vmid)  # idempotent, correct node
    logger.info("reaper.destroyed", extra={"vmid": vmid})
```

Add a real-provider regression that places the orphan on a node other than
`default_node` and asserts the DELETE targets that node (the Fake must also start
honoring/validating `node` in `destroyCt`, or the test must use a stub that records
the `(node, vmid)` pair). For a strict single-node v1 the cheaper alternative is to
**reject non-`default_node` creates at the boundary** so the hardcode is provably
safe — but that constraint must be enforced and tested, not assumed.

## Warnings

### WR-01: `bootconfig.persisted` event leaks `project_repo`/`config_repo` un-redacted into UI-rendered data

**File:** `api/services/workspaceService.py:408-417`
**Issue:**
`_persist_boot_intent` writes the repo identifiers straight into event `data` with
no redaction:

```python
await self.db.logEvent(
    ws.id, "bootconfig.persisted",
    {"config_repo": ..., "project_repo": config.project_repo, ...},
)
```

`project_repo` is free-form user input (`WorkspaceCreate.project_repo`, no
validation rejecting URL userinfo). `GET /workspaces/{id}/events` returns this
verbatim (`routers/workspaces.py:88-98`) and `ActivityDrawer.dataSummary` renders
every `data` value as text (`ActivityDrawer.tsx:156-161`). Meanwhile
`ui/src/types/event.ts:7-8` states `data` is "the already server-redacted
(`_safe()`) payload — the UI renders it verbatim". That contract is **false** for
this event type: a repo URL like `https://user:ghp_xxx@github.com/acme/r.git`
lands and renders unredacted. `test_reaper_timed_out_event_carries_no_secret`
seeds exactly such a `project_repo` but only inspects `reaper.*` events
(`test_reconciler.py:281`), so this path is untested.

**Fix:**
Route the repo fields through `_safe()` (or a dedicated non-exception redactor)
before logging, OR validate `project_repo` at the boundary to reject embedded
userinfo. Smallest correct fix — redact at the event boundary:

```python
def _redact_repo(url: str) -> str:
    return _URL_USERINFO.sub("://" + _REDACTED + "@", url)[:200]

await self.db.logEvent(ws.id, "bootconfig.persisted", {
    "config_repo": _redact_repo(config.config_repo),
    "project_repo": _redact_repo(config.project_repo),
    "config_branch": config.config_branch,
    "project_branch": config.project_branch,
})
```

Add a regression asserting a userinfo-bearing `project_repo` is `[redacted]` in the
`bootconfig.persisted` event.

### WR-02: One raising idle-stop aborts the rest of the auto-stop pass

**File:** `api/services/reconciler.py:133-140`
**Issue:**
`_auto_stop` snapshots `listWorkspaces(status="running")` once, then loops calling
`self.service.stopWorkspace(row.id, reason="idle")`. Between the snapshot and the
stop, a workspace can leave `running` (an operator stop, a destroy). `stopWorkspace`
re-reads under the lock and runs `assert_transition(ws.status, "stop")`
(`workspaceService.py:247`), which raises `IllegalTransitionError` for a now-stopped
row. That exception propagates out of `_auto_stop` → `reconcile_once` → caught only
by `_reconcile_loop`'s broad `except` (`main.py:167`). The loop survives, but every
**remaining** idle workspace in this pass is skipped until the next cadence tick
(default 60s). A single transient race silently delays auto-stop fleet-wide for a
period.

**Fix:**
Isolate each stop so one failure does not abort the batch:

```python
for row in await self.db.listWorkspaces(status="running"):
    ...
    if self._now() - last_disconnect > window:
        try:
            await self.service.stopWorkspace(row.id, reason="idle")
        except IllegalTransitionError:
            continue  # raced out of running between snapshot and stop — fine
```

(Keep genuinely unexpected errors propagating, or log-and-continue per the loop's
own resilience contract.)

### WR-03: ActivityDrawer focus trap is escapable via the scrim button

**File:** `ui/src/components/ActivityDrawer.tsx:284-298, 305-320`
**Issue:**
The focus trap's `querySelectorAll` scopes to `drawerRef.current` (the `<aside>`)
only (`:284`), but the dismiss scrim is a real focusable `<button>` rendered
*before* the aside and *outside* its subtree (`:305-320`). A `role="dialog"
aria-modal="true"` is asserted (`:323-324`), but Tab can land on the scrim button,
which is not in the trap's focusables list, so the "keep Tab within the drawer"
guarantee is broken — and a screen reader exposes an interactive control outside
the modal. The component docstring claims a working "focus trap" (`:15`).

**Fix:**
Either give the scrim `tabIndex={-1}` and `aria-hidden="true"` (it is redundant
with the Esc/× affordances for keyboard users), or move the scrim inside the
trapped subtree, or query focusables document-wide and constrain to the dialog.
Smallest fix:

```tsx
<button type="button" aria-label="Dismiss activity log" onClick={onClose}
        tabIndex={-1} aria-hidden="true" style={{ ... }} />
```

### WR-04: `useWorkspaceEvents` keeps polling a 404'd / deleted workspace

**File:** `ui/src/hooks/useWorkspaceEvents.ts:26-33`
**Issue:**
`refetchInterval: POLL_INTERVAL_MS` is unconditional, so the query keeps polling
every 3s while the drawer is open even when the endpoint returns an error (e.g. the
workspace was destroyed and `GET /workspaces/{id}/events` now 404s, or the worker is
down). The drawer shows the retry strip (`ActivityDrawer.tsx:343-358`) but never
backs off — a permanently-gone workspace generates an indefinite 3s error-poll for
as long as the drawer stays open. This is a robustness/noise issue, not a
correctness one, but it contradicts the "one live tempo, gated on open" intent.

**Fix:**
Gate `refetchInterval` on success (TanStack supports a function form), or stop
polling after N consecutive failures:

```ts
refetchInterval: (query) => (query.state.status === "error" ? false : POLL_INTERVAL_MS),
```

## Info

### IN-01: Reaper docstring/comment says `reaper.destroyed`; UI never receives it as an event

**File:** `api/services/reconciler.py:104`
**Issue:** The orphan branch logs `reaper.destroyed` to the structured logger (correct
— a row-less reap has no events FK). The `events.ts` badge map handles `reaper.*`
generically (`events.ts:72-76`), so this string is consistent *if* it ever became a
DB event, but by design it never does. Harmless, but the asymmetry (one reaper
outcome is a DB event, the other only a log line) is worth a one-line note in the
module docstring so a future reader does not look for `reaper.destroyed` in the UI.
**Fix:** Add a sentence to the `_reap` docstring noting `reaper.destroyed` is
log-only by construction (no live `workspaceId` to satisfy the events FK).

### IN-02: `_safe` entropy backstop redacts any 32+ char token, including non-secret IDs

**File:** `api/services/workspaceService.py:62`
**Issue:** `re.compile(r"\b[A-Za-z0-9_-]{32,}\b")` will redact a 32-char hex commit
SHA, a UUID-without-dashes, or a long branch name in an exception message. This is a
deliberate conservative backstop (over-redaction beats a leak), so it is correct by
intent — flagged only so the over-redaction is a known tradeoff, not a surprise in
triage.
**Fix:** None required; optionally document the tradeoff inline.

### IN-03: `dataSummary` JSON-stringifies nested objects, producing dense unreadable rows

**File:** `ui/src/components/ActivityDrawer.tsx:157-161`
**Issue:** For an event whose `data` value is itself an object/array, the summary
renders `key: {"nested":"json"}`. Functionally fine and XSS-safe (React escapes the
text node), but for a deeply-nested redacted payload the row becomes hard to read.
Cosmetic.
**Fix:** Optionally truncate/flatten nested values, or render only scalar leaves.

### IN-04: `injectBootConfig` is dead across the saga but retained on both providers

**File:** `api/services/workspaceService.py:149` (calls `_persist_boot_intent`, not
`injectBootConfig`); `api/compute/provider.py:100-108`, `fakeProvider.py:125-128`,
`proxmoxProvider.py:205-212`
**Issue:** The create saga deliberately no longer calls `injectBootConfig` (pull-at-
boot via `_persist_boot_intent`), yet the method remains on the ABC and both impls
as a no-op seam. This is documented as an intentional contract seam for a future
push-based backend, so it is acceptable per YAGNI's "one real future use" bar being
explicitly recorded — flagged only as dead-on-the-hot-path code a reader may trip
over.
**Fix:** None required; the retention is documented. Revisit if no push backend
materializes.

---

_Reviewed: 2026-06-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
