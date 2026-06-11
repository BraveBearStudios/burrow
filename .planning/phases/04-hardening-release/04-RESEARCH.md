<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 4: Hardening & Release - Research

**Researched:** 2026-06-11
**Domain:** in-process async reconciliation (reaper + idle auto-stop), atomic capacity-check+reserve, a read-only event-log drawer (React/TanStack Query), and the container supply-chain release path (Dockerfiles, Trivy, syft SBOM, cosign keyless, SLSA provenance, GHCR)
**Confidence:** HIGH (the codebase seams, the CI/CD spec, and the supply-chain tooling are all authoritative or verified; the one residual unknown is real-Proxmox behavior, which is explicitly the dev-homelab smoke, not CI)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Reconciler — Reaper + Auto-stop runtime (CAP-02, CAP-03)**
- A **single in-process asyncio periodic reconciler** (started/stopped via the FastAPI lifespan) performs BOTH reaping and idle auto-stop. No external cron/systemd timer; one loop, two responsibilities (KISS for the single self-host process).
- Reaper scope is all three reconciliations (SC-1/SC-11): destroy Proxmox CTs in the worker pool that have **no owning DB row**, free leaked VMIDs, and mark timed-out `creating` rows `error` (destroying their CTs). Idempotent destroy (destroy of a missing CT is a no-op, Pitfall 7).
- Safety bound: the reaper only ever destroys a CT whose VMID is **in the configured worker pool range AND has no live owning row** — it never touches out-of-pool CTs. Each action emits a structured `reaper.*` event (redacted, no secrets/topology).
- Intervals are configurable with defaults: reconciler period ~60s, `creating`-row timeout ~300s, idle auto-stop window ~30 min. (Exact values at Claude's discretion within these.)

**Auto-stop semantics + capacity concurrency (CAP-02)**
- Idle = **no active terminal WebSocket connection for longer than the window while the workspace is `running`**, reconciled with the SC-8 detach semantics: idle is the *intentional* lifecycle end, NOT an accidental socket drop (a brief disconnect/reconnect must not trip it).
- Idle is derived from the **terminal connect/disconnect events already in the event log** (last disconnect timestamp + no currently-active connection) — no new schema column.
- Auto-stop action is **STOP, not destroy** — the workspace is preserved and restartable; it emits `workspace.stopped` with `reason: idle`, consistent with detach-not-terminate.
- Capacity-under-concurrency fix: make the **capacity check + VMID reservation atomic** (a single DB transaction / lock around check-then-reserve) so two concurrent creates cannot both pass the node-RAM check and overcommit the node. (The VMID partial-unique INSERT is already race-safe; the *capacity check* is the unserialized gap being closed.)

**Event Drawer UI (UI-06)**
- Surface: a **right-side slide-in drawer**, opened per-workspace from the workspace row/panel header, showing the full event log.
- Data: **poll `GET /api/v1/workspaces/{id}/events`** via TanStack Query with a `refetchInterval` while the drawer is open, reusing the existing `ui/src/api/client.ts` + hook pattern (e.g. mirror `useWorkspaces`). No new streaming endpoint.
- Row format: **newest-first**; each row shows a timestamp, a color-coded type badge, and the redacted `data` summary; `boot.error` is visually emphasized.
- Styling honors the design handoff (`design/Burrow-handoff/` + `docs/design/` tokens) and matches the existing react-mosaic/xterm app shell.

**Images & Release supply-chain (CICD-04, CICD-05)**
- Dockerfiles (per `docs/ci-cd-and-testing.md` §2.2): **multi-stage, base image pinned by digest** (`@sha256:…`, not a tag), **non-root** user, read-only root FS where possible, a `HEALTHCHECK` (`api`: `GET /health`; `ui`: nginx 200 on `/`), and OCI source/revision labels (AGPL §13).
- Image scan: **Trivy, fail on HIGH and CRITICAL** (no unwaived findings), results uploaded as **SARIF** to GitHub code scanning, run in the build job (CICD-04).
- Release path (`release.yml`, triggered on release published / tag `v*`): **syft SBOM in SPDX + CycloneDX**, **cosign keyless** signing by digest (Sigstore + GitHub OIDC, no long-lived keys), and a **SLSA build-provenance attestation**, then **push to GHCR** with least-privilege per-job `permissions` and third-party actions **SHA-pinned** (Pitfall 14).
- Workflow split: `ci.yml` builds + scans on PR **without pushing**; `release.yml` owns SBOM/sign/provenance/GHCR-publish (ci-cd §3.1). v1 stays LAN-only — no public exposure (Pitfall 12).

### Claude's Discretion
- Exact reconciler interval/timeout/window values within the ranges above, the precise drawer animation/markup, the SQL/locking mechanism for the atomic capacity check, and the Dockerfile layer structure are at Claude's discretion, guided by the spec and existing conventions.

### Deferred Ideas (OUT OF SCOPE)
- Real-Proxmox acceptance of reaper / auto-stop / capacity-under-concurrency — dev-homelab smoke gate, not CI.
- harden-runner egress allowlist, vuln-waiver allowlist format/expiry policy — open items noted in PROJECT.md; adopt-now-vs-defer is a release-polish decision, not core to this phase.
- Auto-select worker node / multi-node capacity — out of scope (v1 operator picks the node).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAP-02 | Idle workspaces (no active terminal connection beyond a configured window) are auto-stopped | Idle-derivation algorithm over the existing `terminal.connected` / `terminal.disconnected` event log (Pattern 3); reconciler emits `workspace.stopped` with `reason: idle`; reuses `WorkspaceService.stopWorkspace`. Hermetic test via injected event fixtures + a single reconcile pass. |
| CAP-03 | A reaper reconciles and destroys orphaned LXCs and frees leaked VMIDs (SC-9) | Reaper algorithm over `compute.usedVmids()` ∩ pool-range minus `_db_used_vmids()` (Pattern 2); reuses idempotent `destroyCt` + `_safe`-redacted `reaper.*` events; timed-out `creating` rows. Hermetic test injects an orphan into the Fake's `_containers` + a stale `creating` row. |
| UI-06 | A per-workspace activity drawer surfaces the event log | `useWorkspaceEvents` mirrors `useWorkspaces` with `enabled = drawerOpen && !!id`; client-side `.reverse()` of the oldest-first endpoint; `EVENT_BADGE` map keyed on the real namespaced types; focus-trap dialog. Full contract in 04-UI-SPEC.md (Pattern 4). |
| CICD-04 | CI builds both images multi-stage, digest-pinned, non-root, with HEALTHCHECKs; image scan fails on HIGH/CRITICAL | `Dockerfile.api` + `Dockerfile.ui` per ci-cd §2.2; Trivy two-run pattern (table+exit-code AND sarif) to satisfy both the HIGH/CRITICAL gate and the SARIF upload (Pitfall 16); build job in `ci.yml` with no push (Pattern 6). Fully CI-verifiable. |
| CICD-05 | The release path emits an SBOM (syft), a cosign keyless signature, and SLSA build provenance, and publishes to GHCR | `release.yml` on tag `v*`: build+push to GHCR by digest → `anchore/sbom-action` (SPDX + CycloneDX) → `cosign sign` keyless (OIDC) → `actions/attest-build-provenance` push-to-registry; per-job least-priv `permissions` (Pattern 7). Fully CI-verifiable (GHCR is real, but it is the project's own registry, not external infra). |

> The capacity-race fix is the *atomic* half of CAP-01 (already shipped); CONTEXT files it under CAP-02's hardening scope. It is not a separately-numbered requirement but is a locked decision the planner MUST cover.
</phase_requirements>

## Summary

Phase 4 has two unrelated halves bridged by one UI surface. The **runtime-hardening half** (reaper, idle auto-stop, capacity-race fix) is pure backend orchestration that plugs into seams that already exist: the `ComputeProvider` (`usedVmids`, idempotent `destroyCt`), the `DbProvider` (`listWorkspaces`, `getEvents`, `updateWorkspace`), and `WorkspaceService` (`stopWorkspace`, `_compensate`, `_safe`, `_db_used_vmids`). The new code is (a) a `Reconciler` class with a single `reconcile_once()` method that does both reaping and idle-detection, and (b) a FastAPI `lifespan` that spawns/cancels a periodic loop calling it. The **supply-chain half** (Dockerfiles, Trivy, SBOM, cosign, SLSA, GHCR) is config/YAML that follows `docs/ci-cd-and-testing.md` §2 / §5 verbatim. The **UI surface** (UI-06 drawer) is fully specified in 04-UI-SPEC.md and reuses the Phase-2 design system + the `useWorkspaces` TanStack pattern.

The single most important design discipline is **testability without a real clock or Proxmox**. Every reconcile decision must be a pure function of (DB state, compute state, a passed-in `now`), so the test drives one `reconcile_once(now=...)` pass over the Fake provider and asserts the effects — no `asyncio.sleep`, no wall-clock, no `freezegun`. The periodic loop is a thin wrapper the lifespan owns; it is tested separately (and minimally) for clean start/cancel, not for its timing.

**Primary recommendation:** Build a `Reconciler(compute, db, settings, now=...)` service with a single `async reconcile_once()` that returns a structured summary, started by a `lifespan` that `asyncio.create_task`s a `while True: await reconcile_once(); await asyncio.sleep(period)` loop and `cancel()`s it on shutdown. Make the capacity-check+reserve atomic by moving the capacity guard *inside* the reservation retry under a single `BEGIN IMMEDIATE` SQLite transaction (or a process-level `asyncio.Lock` for the single-process v1, the simpler KISS option). Build the drawer per 04-UI-SPEC. Build `Dockerfile.api`/`Dockerfile.ui` + extend `ci.yml` with a build+Trivy job and add a new `release.yml`. Add **no new runtime PyPI/npm dependency** — the whole phase reuses existing libs plus SHA-pinned GitHub Actions.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Periodic reconcile loop (reaper + auto-stop) | API / Backend (FastAPI lifespan + asyncio task) | — | Single self-host process; no external scheduler. CONTEXT locks "in-process asyncio". The loop owns the cadence; the decision logic is a pure service. |
| Reaper (orphan CT destroy, leaked VMID free, timed-out `creating`) | API / Backend (`Reconciler` over `ComputeProvider` + `DbProvider`) | Compute provider (`destroyCt`, `usedVmids`) | The set-difference (pool CTs minus live DB rows) and the safety bound live in the service; the provider only executes the idempotent destroy. Seam discipline: no `proxmoxer` symbols escape. |
| Idle detection | API / Backend (`Reconciler` reading the event log) | DB (`getEvents`) | Derived from `terminal.connected`/`disconnected` events already persisted; no new schema column. Decision is service policy. |
| Capacity-check + VMID-reserve atomicity | API / Backend (`WorkspaceService` create path) | DB (transaction / lock) | The unserialized gap is between the in-service capacity read and the DB INSERT. Closing it is a service+DB concern, never the UI's. |
| Activity drawer (event log view) | Browser / Client (React component + TanStack Query poll) | API (`GET /workspaces/{id}/events`, already shipped) | Read-only view of an existing endpoint. No new backend route. Poll cadence + reverse + badge map are client-side. |
| Image build + vuln scan | CI (GitHub Actions `ci.yml` build job) | — | Builds the production Dockerfiles with Buildx; Trivy scans the built image. CI-verifiable; no push on PR. |
| SBOM + sign + provenance + GHCR publish | CI (GitHub Actions `release.yml`) | GHCR (registry) | Triggered on `v*` tag; least-priv per-job tokens; keyless OIDC. CI-verifiable against the project's own registry. |

## Standard Stack

### Core (already in the repo — REUSE, do not add)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.136.3 `[VERIFIED: api/pyproject.toml]` | `lifespan` async context manager hosts the reconciler task | The modern, idiomatic startup/shutdown hook (replaces deprecated `@app.on_event`). `[CITED: fastapi.tiangolo.com/advanced/events]` |
| `uvicorn[standard]` | 0.49.0 `[VERIFIED: api/pyproject.toml]` | ASGI server; runs the event loop the reconciler task is scheduled on | Already the server; the lifespan task rides its loop. |
| `aiosqlite` | 0.22.1 `[VERIFIED: api/pyproject.toml]` | The atomic capacity-check+reserve transaction lives here | Already the v1 store; WAL + busy_timeout already configured (`sqliteProvider._connect`). |
| `httpx` | 0.28.1 `[VERIFIED: api/pyproject.toml]` | (no new use this phase) | — |
| `@tanstack/react-query` | (in `ui/package.json`) `[VERIFIED: ui/src/hooks/useWorkspaces.ts]` | `useWorkspaceEvents` poll with `enabled`-gated `refetchInterval` | Already the data-fetch layer; the drawer mirrors `useWorkspaces`. |
| React 19 / Vite / TypeScript / Tailwind v4 | (Phase-2 stack) `[VERIFIED: STATE.md decisions]` | The drawer component + tokens | The drawer is additive on the established shell; 04-UI-SPEC forbids any new runtime UI dep. |

### Supporting (CI tooling — GitHub Actions, NOT registry packages)

| Action / Tool | Version (pin to SHA) | Purpose | When to Use |
|---------------|----------------------|---------|-------------|
| `docker/setup-buildx-action` | latest stable, SHA-pinned `[ASSUMED]` | Buildx for multi-stage reproducible builds | Both `ci.yml` build job and `release.yml`. |
| `docker/build-push-action` | latest stable, SHA-pinned `[ASSUMED]` | Build (PR, no push) and build+push (release, by digest) | `push: false` in ci.yml; `push: true` in release.yml. |
| `docker/login-action` | latest stable, SHA-pinned `[ASSUMED]` | Authenticate to GHCR with `GITHUB_TOKEN` | `release.yml` only. |
| `docker/metadata-action` | latest stable, SHA-pinned `[ASSUMED]` | OCI labels + tag computation (§2.4 table) | Both workflows (labels); release for tags. |
| `aquasecurity/trivy-action` | ~v0.36.x, SHA-pinned `[CITED: github.com/aquasecurity/trivy-action]` | Image vuln scan, fail on HIGH/CRITICAL, SARIF | `ci.yml` build job (CICD-04). |
| `github/codeql-action/upload-sarif` | latest, SHA-pinned `[CITED: trivy-action README]` | Upload the Trivy SARIF to GitHub code scanning | After the SARIF-format Trivy run, `if: always()`. |
| `anchore/sbom-action` | latest (syft ≥ 1.42) SHA-pinned `[CITED: github.com/anchore/sbom-action]` | syft SBOM in SPDX + CycloneDX | `release.yml` (CICD-05). |
| `sigstore/cosign-installer` + `cosign sign` | cosign ≥ v2, SHA-pinned installer `[CITED: github.com/sigstore/cosign]` | Keyless signing of the image by digest via OIDC | `release.yml`, needs `id-token: write` + `packages: write`. |
| `actions/attest-build-provenance` | v1+ (or v2), SHA-pinned `[CITED: github.com/actions/attest-build-provenance]` | SLSA build-provenance attestation bound to the image digest | `release.yml`, needs `attestations: write` + `id-token: write` + `packages: write` (for `push-to-registry`). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Atomic capacity via `BEGIN IMMEDIATE` transaction | A process-level `asyncio.Lock` around the whole create-reserve sequence | v1 is a single self-host process. A `asyncio.Lock` is simpler (KISS) and sufficient *if* `uvicorn --workers 1`; CONTEXT's "single DB transaction / lock" allows either. Prefer the lock for simplicity but document the `--workers >1` caveat (the lock is per-process; the DB transaction is the cross-process backstop). The VMID INSERT is already cross-process race-safe; only the capacity *read* is unserialized. |
| Trivy | Grype | ci-cd §5.2 names "Trivy/Grype"; Trivy has first-class SARIF + the official action. Use Trivy. |
| `cosign` keyless | `actions/attest-build-provenance` alone | Provenance ≠ a Sigstore image signature. CICD-05 requires BOTH a cosign signature AND a SLSA provenance attestation. Do both. |
| `freezegun` / `time-machine` for idle-window tests | Inject a `now` callable into the `Reconciler` | Injecting `now` keeps the test a pure single-pass assertion with zero new deps and zero monkeypatching of the system clock. STRONGLY prefer dependency injection over a time-mock library (see Don't Hand-Roll). |
| `python:3.12-slim` runtime | distroless | ci-cd §9 Open Q1: start slim (debuggable), move to distroless once runtime deps stable. Use slim for v1. |

**Installation (runtime deps): NONE.** The reconciler, capacity fix, and drawer add no new PyPI or npm runtime package. CI tooling is GitHub Actions referenced by SHA in workflow YAML, not installed into the app. If the planner decides a time-test helper is unavoidable (it should not be), `freezegun==1.5.5` `[ASSUMED]` is the registry-current option — but the injected-`now` approach removes the need.

**Version verification performed:**
- `freezegun` latest = 1.5.5, `time-machine` latest = 3.2.0 (`pip index versions`, 2026-06-11) — listed only to document the rejected alternative.
- syft current = 1.42.0 (Feb 2026) `[CITED: anchore/syft releases]`.
- Trivy action examples reference v0.36.0 `[CITED: trivy-action]`.
- All GitHub Actions versions are `[ASSUMED]` until the planner pins exact SHAs at write time (the repo convention is SHA-pin + trailing version comment, already used in `ci.yml`).

## Package Legitimacy Audit

> This phase installs **no new runtime registry packages**. The CI additions are GitHub Actions referenced by commit SHA in workflow YAML — they are not npm/PyPI installs and are governed by the repo's existing SHA-pin convention (`ci.yml` header), not by slopcheck.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| *(none — no new runtime dep)* | — | — | — | — | n/a | — |
| `freezegun` (rejected alt) | PyPI | mature (1.5.5, many releases since 2015) | very high | github.com/spulec/freezegun | not run (unavailable) | NOT ADDED — superseded by injected `now` |

**Packages removed due to slopcheck [SLOP] verdict:** none (no packages proposed).
**Packages flagged as suspicious [SUS]:** none.

*slopcheck was not installable in this environment. Because this phase proposes **zero** new runtime registry packages, there is nothing to gate. The GitHub Actions added in CI MUST be SHA-pinned (the repo's existing security control, ci-cd §5.5 / Pitfall 14); the planner pins each to a full commit SHA with a trailing version comment, exactly as the current `ci.yml` does. Treat every new action reference as `[ASSUMED]` until its SHA is pinned and its repo verified.*

## Architecture Patterns

### System Architecture Diagram

```
RUNTIME-HARDENING HALF (in-process, hermetic over the Fake in CI)

  uvicorn event loop
        │
        ▼
  FastAPI lifespan ──(startup)──► asyncio.create_task(reconcile_loop)
        │                                   │
        │                          ┌────────┴─────────┐
        │                          │  while not stop: │
        │                          │   reconcile_once()│◄──── injected now()
        │                          │   await sleep(P)  │
        │                          └────────┬─────────┘
        │                                   ▼
        │              ┌──────────── Reconciler.reconcile_once() ──────────────┐
        │              │                                                        │
        │       (A) REAP                          (B) AUTO-STOP                 │
        │       compute.usedVmids() ∩ pool        for ws in running:           │
        │         minus db live vmids             events = db.getEvents(ws.id)  │
        │         → orphan CTs → destroyCt        last_disconnect, no active    │
        │       db rows status=creating           conn, now-last > window       │
        │         older than timeout              → stopWorkspace(reason=idle)  │
        │         → destroyCt + status=error      → workspace.stopped{idle}     │
        │       → reaper.* events (redacted)                                    │
        │              └──────────────┬───────────────────────────────────────┘
        │                             ▼
        │                  ComputeProvider (Fake in CI │ Proxmox in homelab)
        │                  DbProvider (SQLite)
        │
        └──(shutdown)──► task.cancel(); await task  (swallow CancelledError)


CREATE PATH (atomic capacity-check+reserve)

  POST /workspaces ─► WorkspaceService.createWorkspace
        │
        ▼
   ┌─ async with create_lock (or BEGIN IMMEDIATE txn) ─┐
   │   getNodeMemory > threshold?  → CapacityError     │   ← check + reserve
   │   reserve VMID via partial-unique INSERT          │     are now ONE
   └───────────────────────────────────────────────────┘     critical section
        │ (clone → boot → running, unchanged)


UI: ACTIVITY DRAWER (read-only)

  TerminalPanel header [activity icon] ──click──► setActiveEventsWorkspaceId(id)
        │
        ▼
   ActivityDrawer (right-anchored aside, role=dialog)
        │  useWorkspaceEvents(id, enabled = open && !!id)
        ▼
   TanStack useQuery(refetchInterval 3000ms) ─► GET /api/v1/workspaces/{id}/events
        │   (endpoint = oldest-first)
        ▼
   [...events].reverse()  → EVENT_BADGE[type] → rows (newest-first)


SUPPLY-CHAIN (CI)

  PR  ─► ci.yml: gates → tests → build(no push) → Trivy(fail HIGH/CRIT)+SARIF
  tag v* ─► release.yml: build+push GHCR(digest) → syft SBOM → cosign sign → attest provenance
```

### Recommended File Structure (additions)

```
api/
├── services/
│   └── reconciler.py          # NEW: Reconciler.reconcile_once() (reaper + auto-stop)
├── main.py                    # EDIT: add lifespan that owns the reconcile task
├── config.py                  # EDIT: reconciler_period_s, creating_timeout_s, idle_window_s
└── tests/
    ├── unit/
    │   └── test_reconciler.py        # NEW: single-pass reaper + idle decisions over Fake
    └── integration/
        ├── test_capacity_race.py     # NEW: two concurrent creates can't both pass
        └── test_lifespan.py          # NEW (optional): task starts + cancels cleanly

ui/src/
├── components/
│   └── ActivityDrawer.tsx     # NEW: the UI-06 drawer (04-UI-SPEC)
│   └── ActivityDrawer.test.tsx
├── hooks/
│   └── useWorkspaceEvents.ts  # NEW: mirrors useWorkspaces, enabled-gated
├── lib/
│   └── events.ts             # NEW: EVENT_BADGE map (mirrors status.ts pattern)
├── types/
│   └── event.ts              # NEW (or extend workspace.ts): WorkspaceEvent
└── components/TerminalPanel.tsx   # EDIT: add the activity trigger icon button
ui/tests/e2e/
└── activity-drawer.spec.ts   # NEW: Playwright drawer journey over Fake

# repo root
Dockerfile.api                # NEW (ci-cd §2.2)
Dockerfile.ui                 # NEW (ci-cd §2.2)
.dockerignore                 # NEW (excludes .git, .env*, tests, state)
.github/workflows/ci.yml      # EDIT: add build + Trivy job (no push)
.github/workflows/release.yml # NEW: build+push → SBOM → sign → attest → GHCR
```

### Pattern 1: FastAPI lifespan owns a periodic asyncio task

```python
# Source: https://fastapi.tiangolo.com/advanced/events/ (lifespan) + idiomatic
# asyncio.create_task / cancel pattern. The DECISION logic is NOT here — it is in
# Reconciler.reconcile_once(); this wrapper only owns the cadence + lifecycle.
import asyncio
import contextlib
from collections.abc import AsyncIterator
from fastapi import FastAPI

async def _reconcile_loop(reconciler, period_s: float) -> None:
    while True:
        try:
            await reconciler.reconcile_once()
        except Exception:
            logger.exception("reconcile pass failed; continuing")  # one bad pass != loop death
        await asyncio.sleep(period_s)

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    reconciler = build_reconciler()            # compute + db + settings, from the same seams
    task = asyncio.create_task(_reconcile_loop(reconciler, settings.reconciler_period_s))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

# create_app(): app = FastAPI(title=..., version=..., lifespan=lifespan)
```

**What:** A single background task scheduled on uvicorn's loop, cancelled cleanly on shutdown.
**When to use:** The one always-on reconciler. `main.py` currently has NO lifespan — this is the attach point.
**Critical:** wrap the body in a broad `except` so one failed pass (e.g. a transient Proxmox blip in the homelab) does not kill the loop. The loop is intentionally thin; all testable logic lives in `reconcile_once()`.

### Pattern 2: Reaper as a pure single-pass over the seams

```python
# Source: existing seams in this repo (compute.usedVmids, db.listWorkspaces,
# WorkspaceService._compensate / _safe). No new provider method needed.
class Reconciler:
    def __init__(self, compute, db, settings, now=None):
        self.compute, self.db, self.settings = compute, db, settings
        self._now = now or (lambda: datetime.now(timezone.utc))  # INJECTABLE clock

    async def _reap(self) -> None:
        pool = range(self.settings.worker_pool_start, self.settings.worker_pool_end + 1)
        compute_vmids = await self.compute.usedVmids()           # pool-scoped already in Proxmox impl
        rows = await self.db.listWorkspaces()
        live_vmids = {r.vmid for r in rows if r.vmid is not None}

        # (A) Orphan CTs: in the pool, known to compute, but no live DB row → destroy.
        for vmid in sorted(compute_vmids - live_vmids):
            if vmid in pool:                                     # SAFETY BOUND (never out-of-pool)
                await self.compute.destroyCt(self.settings.default_node, vmid)  # idempotent
                # reaper.* event — needs an owning row OR a workspace-less audit sink (see Open Q1)

        # (B) Timed-out creating rows: stuck > creating_timeout → destroy CT + mark error.
        deadline = self._now() - timedelta(seconds=self.settings.creating_timeout_s)
        for r in rows:
            if r.status == "creating" and _parse(r.created_at) < deadline and r.vmid is not None:
                await self.compute.destroyCt(r.node, r.vmid)     # idempotent
                await self.db.updateWorkspace(r.id, {"status": "error"})
                await self.db.logEvent(r.id, "reaper.timed_out", {"reason": "creating timeout"})
```

**What:** The reaper is a set-difference plus a timeout sweep — both pure over the current (DB, compute) state.
**Safety bound (CONTEXT, load-bearing):** only ever destroy a VMID that is BOTH in the pool range AND absent from `live_vmids`. The Proxmox `usedVmids()` is already pool-scoped (`worker_pool_start..end`), but re-assert the bound in the service so the Fake (which is NOT pool-scoped) is also safe.
**Reuse:** `destroyCt` is already idempotent (no-op on a missing CT, Pitfall 7) in BOTH providers — the reaper needs no new compute method. `_safe()` redacts event text.

### Pattern 3: Idle detection from the event log (no new column)

```python
# Idle = workspace is `running`, the LAST terminal event is a `terminal.disconnected`
# (no currently-active connection), and that disconnect is older than the window.
# A brief disconnect→reconnect leaves `terminal.connected` as the last event → NOT idle
# (this is the SC-8 distinction CONTEXT requires).
async def _auto_stop(self) -> None:
    window = timedelta(seconds=self.settings.idle_window_s)
    for r in await self.db.listWorkspaces(status="running"):
        events = await self.db.getEvents(r.id)                  # oldest-first (getEvents contract)
        term = [e for e in events if e.type in ("terminal.connected", "terminal.disconnected")]
        if not term or term[-1].type != "terminal.disconnected":
            continue                                            # connected now (or never) → active
        last_disconnect = _parse(term[-1].created_at)
        if self._now() - last_disconnect > window:
            await self.service.stopWorkspace(r.id)              # REUSE the guarded transition
            # stopWorkspace currently logs workspace.stopped{} — see Open Q2: thread reason=idle
```

**What:** "No active connection beyond the window" derived purely from the last connect/disconnect pair.
**Why it is correct:** a reconnect appends a fresh `terminal.connected`, so `term[-1]` flips back to connected and the workspace is no longer idle. Only a sustained disconnect trips it.
**Reuse:** call `WorkspaceService.stopWorkspace` (not a raw `stopCt`) so the state-machine guard, the per-workspace lock, and `stoppedAt` are all honored. **Caveat (Open Q2):** `stopWorkspace` currently logs `workspace.stopped` with `{}` — auto-stop must emit `reason: idle`. Either add an optional `reason` param to `stopWorkspace` or have the reconciler log the reason. The UI-SPEC badge map keys on `data.reason === "idle"`, so the reason MUST reach the event `data`.

### Pattern 4: Drawer hook — enabled-gated TanStack poll + client reverse

```typescript
// Source: ui/src/hooks/useWorkspaces.ts pattern. enabled gates the poll to "open".
export function useWorkspaceEvents(id: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["workspace-events", id],
    queryFn: () => api<WorkspaceEvent[]>(`/workspaces/${id}/events`),
    refetchInterval: 3000,                 // match the workspace-list cadence
    enabled: enabled && !!id,              // poll ONLY while the drawer is open (04-UI-SPEC crit 5)
  });
}
// In the component: const rows = useMemo(() => [...(data ?? [])].reverse(), [data]);
// (endpoint is oldest-first → reverse client-side for newest-first; 04-UI-SPEC crit 2)
```

**What:** mirrors the established hook; the `enabled` flag is the poll gate; the reverse is the newest-first contract.
**Badge map:** an `EVENT_BADGE` record in `ui/src/lib/events.ts` keyed on the **real namespaced strings** (`workspace.created`, `terminal.connected`, `boot.error`, a `reaper.*` prefix match, and an unknown→raw-mono fallback). 04-UI-SPEC §"Event type → badge color map" is the binding table — copy it verbatim.
**A11y:** `role="dialog"`, focus trap (Tab cycles within), `Esc` closes, focus returns to the trigger, `--accent-line` focus ring, `aria-live="polite"` on the list. Full contract in 04-UI-SPEC §Accessibility.

### Pattern 5: `ci.yml` build + Trivy two-run (CICD-04)

```yaml
# Two Trivy invocations: one fails the build on HIGH/CRITICAL (table, exit-code 1),
# one emits a COMPLETE SARIF for code scanning. A single run can't do both —
# SARIF format ignores the severity filter for exit-code (Pitfall 16).
  build-scan:
    needs: [static-gates]            # extend the existing DAG
    permissions:
      contents: read
      security-events: write         # upload-sarif needs this
    steps:
      - uses: actions/checkout@<sha> # v4.x
      - uses: docker/setup-buildx-action@<sha>
      - uses: docker/build-push-action@<sha>
        with: { context: ., file: ./Dockerfile.api, push: false, load: true, tags: burrow-api:scan }
      - name: Trivy (gate — fail HIGH/CRITICAL)
        uses: aquasecurity/trivy-action@<sha>   # ~v0.36
        with: { image-ref: burrow-api:scan, format: table, severity: 'HIGH,CRITICAL', exit-code: '1', ignore-unfixed: 'false' }
      - name: Trivy (SARIF — full report)
        if: always()
        uses: aquasecurity/trivy-action@<sha>
        with: { image-ref: burrow-api:scan, format: sarif, output: trivy.sarif }
      - uses: github/codeql-action/upload-sarif@<sha>
        if: always()
        with: { sarif_file: trivy.sarif }
```

**What:** PR-time build proves the image builds; Trivy fails on HIGH/CRITICAL; the SARIF run uploads the full report. **No push on PR** (ci-cd §2.4 / §3.1).
**Matrix:** run for both `Dockerfile.api` and `Dockerfile.ui`.

### Pattern 6: `release.yml` (CICD-05)

```yaml
# Source: ci-cd §5.4/§5.5 + actions/attest-build-provenance + sigstore/cosign +
# anchore/sbom-action READMEs. Per-job least-priv permissions.
on: { push: { tags: ['v*'] }, release: { types: [published] } }
jobs:
  publish:
    permissions:
      contents: read
      packages: write          # push to GHCR + push attestation
      id-token: write          # cosign keyless OIDC + provenance
      attestations: write      # actions/attest-build-provenance
    steps:
      - uses: actions/checkout@<sha>
      - uses: docker/login-action@<sha>      # ghcr.io with GITHUB_TOKEN
      - uses: docker/metadata-action@<sha>   # tags X.Y.Z, X.Y, latest, sha-<short>; OCI labels
      - id: build
        uses: docker/build-push-action@<sha> # push: true → outputs digest
      - uses: anchore/sbom-action@<sha>      # format: spdx-json AND a second run cyclonedx-json
      - run: cosign sign --yes ghcr.io/<owner>/burrow-api@${{ steps.build.outputs.digest }}
      - uses: actions/attest-build-provenance@<sha>
        with:
          subject-name: ghcr.io/<owner>/burrow-api
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true
```

**What:** build+push by digest, then SBOM (both formats), keyless cosign signature, SLSA provenance.
**Load-bearing:** sign and attest **by digest** (not a floating tag). `subject-name` must be the fully-qualified GHCR image name for `push-to-registry`. `id-token: write` is mandatory for both cosign keyless and provenance.

### Anti-Patterns to Avoid
- **Putting reconcile decision logic in the loop body.** It becomes untestable without a clock. Keep `reconcile_once()` pure; the loop just calls it.
- **A raw `stopCt`/`destroyCt` in the reconciler bypassing `WorkspaceService`.** It skips the state-machine guard, the per-workspace lock, and the `*_at` timestamps. Auto-stop must go through `stopWorkspace`. (The reaper's orphan-destroy is the exception: orphans have no live row, so there is no state machine to guard — call `destroyCt` directly with the safety bound.)
- **One Trivy run for both gate + SARIF.** The SARIF format ignores the severity-scoped exit-code (Pitfall 16). Two runs.
- **Signing/attesting a tag instead of a digest.** Tags float; the signature/provenance must bind the immutable digest.
- **`verify_ssl=False` creeping into any new Proxmox call.** Not applicable this phase (reconciler reuses the existing provider), but the reaper must not add a new `proxmoxer` import — it goes through `ComputeProvider` only (seam-leakage guard will fail otherwise).
- **Animating every drawer row on each poll.** New rows must use stable `event.id` keys so existing rows don't re-mount/flash (04-UI-SPEC §populated).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idle-window time control in tests | A real `asyncio.sleep`-driven wait, or `freezegun`/`time-machine` | Inject a `now` callable into `Reconciler` and pass an explicit timestamp per pass | Pure, deterministic, zero new deps, no global clock monkeypatch. The test sets `now` to "31 min after last disconnect" and asserts one stop. |
| Orphan-CT teardown | A new "force delete" path | The existing idempotent `destroyCt` (no-op on missing, stop-then-destroy on running, in both providers) | Already handles the running/locked/404 cases (Pitfall 7 + CR-03). |
| Cross-process VMID race | New locking | The shipped `002` partial-unique INSERT (`VmidTakenError` → retry) | Already the race arbiter (SC-3/SC-4). Phase 4 only needs to serialize the *capacity read*. |
| Secret redaction in `reaper.*` events | A new scrubber | The existing `_safe()` in `workspaceService.py` | Already strips git/CI tokens, URL userinfo, long opaque tokens; caps length. Export/reuse it. |
| SBOM generation | A custom dependency walker | `anchore/sbom-action` (syft) | Standard, dual-format (SPDX + CycloneDX), attestable. |
| Image signing | A bespoke GPG key in CI secrets | cosign **keyless** (OIDC, no long-lived key) | ci-cd §5.4 mandates keyless; a stored key is a liability v1 explicitly avoids. |
| Build provenance | Hand-written in-toto JSON | `actions/attest-build-provenance` | Generates + signs SLSA provenance bound to the digest; GitHub-native. |
| Drawer focus trap | A new a11y library | A small `useEffect` keydown handler + focusable-element cycling (the modal already does Esc) | 04-UI-SPEC forbids a new runtime UI dep; the existing `NewWorkspaceModal` already establishes the Esc-to-close pattern to mirror. |

**Key insight:** Phase 4 is overwhelmingly *assembly of existing seams + standard CI tooling*. The temptation to add a scheduler library, a time-mock library, a drawer/dialog component library, or a custom signing key are all traps — every one has a zero-new-dependency answer already present in the codebase or in a SHA-pinned GitHub Action.

## Runtime State Inventory

> This is a hardening/reconciliation phase, not a rename. It nonetheless touches runtime state directly (it destroys CTs and stops workspaces), so the inventory is relevant — but as "what state does the reaper act on," not "what cached string survives a rename."

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Workspace rows in SQLite (`workspaces`), event rows (`events`). The reaper READS `listWorkspaces`/`getEvents` and WRITES `status=error` on timed-out creating rows + `reaper.*` / `workspace.stopped{idle}` events. | Code only — no schema migration. CAP-02/03 use existing columns + the event log (CONTEXT: "no new schema column"). |
| Live service config | Proxmox CTs in the worker-pool VMID range (`worker_pool_start..end`). The reaper DESTROYS pool CTs with no live DB row. In CI these are entries in the Fake's `_containers` dict; in the homelab they are real LXCs. | None to migrate; this IS the reaper's job. The safety bound (pool-range + no-live-row) is the guardrail against destroying an out-of-pool CT. |
| OS-registered state | None. The reconciler is an in-process asyncio task on uvicorn's loop — no systemd timer, no cron, no Task Scheduler entry (CONTEXT explicitly rejects an external scheduler). | None — verified by the "single in-process asyncio reconciler" decision. |
| Secrets/env vars | New `Settings` keys only: `reconciler_period_s`, `creating_timeout_s`, `idle_window_s` (non-secret, placeholder defaults). The Proxmox token + `git_credential_token` are unchanged. | Add the three keys to `config.py` with safe defaults; no secret introduced. The CI release path uses the built-in `GITHUB_TOKEN` (OIDC) — no new long-lived secret (keyless cosign). |
| Build artifacts | NEW: container images `ghcr.io/<owner>/burrow-api` + `burrow-ui`, their SBOMs, signatures, and provenance attestations in GHCR. These are *produced*, not pre-existing stale state. | The release.yml produces them; nothing stale to clean. Pin deployment configs to the digest, not a floating tag (ci-cd §2.4). |

**Nothing found in OS-registered state:** None — verified by the in-process-asyncio decision (no external scheduler is registered).

## Common Pitfalls

### Pitfall 1: The reaper races the create saga and destroys a half-cloned-but-valid CT
**What goes wrong:** The create saga clones a CT and is mid-boot; the reconciler runs, sees a pool CT, and (if it only checked compute) destroys it.
**Why it happens:** The saga persists the `creating` row + reserved VMID BEFORE the clone (SC-2), so a correctly-running saga's VMID IS in `live_vmids`. The danger is only if the reaper checks compute-minus-DB at a moment the row exists.
**How to avoid:** Reap is `compute_vmids - live_vmids` where `live_vmids` includes `creating` rows. A saga in flight has its row → not an orphan. The timed-out-`creating` sweep uses a generous `creating_timeout_s` (~300s, well beyond a normal create) so an in-progress create is never swept. The DB read inside one `reconcile_once` is a consistent snapshot.
**Warning signs:** A test where a `creating` row younger than the timeout gets reaped — that is the regression to guard against.

### Pitfall 2: Auto-stop kills a workspace during a brief reconnect
**What goes wrong:** A user's terminal drops for 5 seconds (network blip) and reconnects; if idle were "any disconnect older than window," a stale-but-reconnected session could be stopped.
**Why it happens:** Naively keying on "a disconnect event exists" instead of "the LAST terminal event is a disconnect."
**How to avoid:** Idle requires `term[-1].type == "terminal.disconnected"`. A reconnect appends `terminal.connected`, flipping the last event back to connected → not idle (Pattern 3, the SC-8 distinction CONTEXT mandates).
**Warning signs:** A test with connect→disconnect→connect within the window that still trips auto-stop.

### Pitfall 3: `reaper.*` and `workspace.stopped{idle}` events have no owning row (orphans)
**What goes wrong:** `db.logEvent(workspace_id, ...)` requires a `workspaceId` FK (events table FK to workspaces). An orphan CT, by definition, has no live row — so where does its `reaper.destroyed` event go?
**Why it happens:** The events table is per-workspace; a leaked VMID with no row can't satisfy the FK.
**How to avoid:** TWO distinct cases. (a) Timed-out `creating` rows and idle auto-stops DO have a row → log normally. (b) A truly orphaned CT (no row ever, or a hard-deleted one) has nowhere to log a per-workspace event → emit a **structured log line** (`logger.info("reaper.destroyed", extra={"vmid": ...})`) instead of a DB event, OR log against the soft-deleted tombstone row if one exists. **This is Open Q1 — the planner must decide the audit sink for row-less reaper actions.** The UI drawer only shows per-workspace events, so a row-less orphan reap is correctly invisible there (it has no workspace to view); structured logs are its audit trail.
**Warning signs:** A `logEvent` call with a `workspace_id` that was just soft-deleted/never existed → FK violation or silent drop.

### Pitfall 4: The lifespan task swallows shutdown or leaks on cancel
**What goes wrong:** On app shutdown the task isn't cancelled (leaks) or its `CancelledError` propagates and dirties the shutdown.
**How to avoid:** `task.cancel()` then `with contextlib.suppress(asyncio.CancelledError): await task` in the lifespan `finally` (Pattern 1). The loop body wraps each pass in a broad `except` so a single failed pass doesn't kill the loop before shutdown.
**Warning signs:** A test that starts the app, triggers shutdown, and finds the task still pending — or a `CancelledError` surfacing in shutdown logs.

### Pitfall 5: Capacity check + reserve still race because only the INSERT was serialized
**What goes wrong:** Two creates both read `getNodeMemory` (under threshold), both proceed to reserve different VMIDs, both clone — overcommitting the node. The partial-unique INSERT only stops two creates from taking the SAME VMID, not from both passing the capacity gate.
**Why it happens:** The capacity read and the reservation are separate, unserialized steps in `createWorkspace` (step 0 then step 1).
**How to avoid:** Put the capacity check INSIDE the same critical section as the reservation — a process `asyncio.Lock` around `if getNodeMemory > threshold: raise; reserve()` (single-process v1), or a `BEGIN IMMEDIATE` transaction if cross-process serialization is needed under `--workers >1`. CONTEXT allows either; the lock is the KISS choice. Document the `--workers >1` caveat.
**Warning signs:** A deterministic two-task test where both creates pass capacity and both succeed — that is the bug; the fix makes the second one see the updated state (or lose the lock and re-check).

### Pitfall 6: Trivy SARIF run doesn't fail the build / the gate run produces an empty SARIF
**What goes wrong:** `format: sarif` + `exit-code: 1` + `severity: HIGH,CRITICAL` — the SARIF path emits ALL severities and the exit-code stops respecting the filter (confirmed open issue). You either fail on lows or upload an incomplete report.
**How to avoid:** TWO Trivy runs (Pattern 5): run #1 `format: table, severity: HIGH,CRITICAL, exit-code: 1` (the GATE), run #2 `format: sarif` with `if: always()` (the full REPORT) → `upload-sarif`. `[CITED: aquasecurity/trivy-action#309]`
**Warning signs:** A build that goes green with HIGH CVEs present, or a SARIF upload that floods code scanning with LOW noise.

### Pitfall 7: Missing OIDC / packages permissions break keyless signing silently
**What goes wrong:** cosign keyless or `attest-build-provenance` fails with an opaque OIDC error because the job lacks `id-token: write` (or `packages: write` for `push-to-registry`).
**How to avoid:** The `publish` job declares exactly `contents: read, packages: write, id-token: write, attestations: write` (Pattern 6). The workflow default stays `contents: read` (ci-cd §5.5). `[CITED: actions/attest-build-provenance README; sigstore/cosign]`
**Warning signs:** "could not fetch OIDC token" / 403 on the GHCR push.

### Pitfall 8: A non-root Dockerfile that can't read its own files / fails HEALTHCHECK
**What goes wrong:** Switching to a non-root `USER` after `COPY` leaves files root-owned and unreadable, or the `HEALTHCHECK` `curl`/`wget` binary is absent in the slim/distroless final stage.
**How to avoid:** `COPY --chown=<user>` (or set ownership before `USER`); for the `api` HEALTHCHECK use Python itself (`python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/api/v1/health')"`) rather than assuming `curl`; for `ui` use the nginx image's available tooling or `wget` if present. Note the health path is `/api/v1/health` (verified in `routers/health.py` mount), not `/health`.
**Warning signs:** Container starts as root (Trivy/Dockle flags it) or the HEALTHCHECK is permanently `unhealthy`.

## Code Examples

### Atomic capacity-check+reserve (the minimal create-path edit)

```python
# Source: this repo's WorkspaceService.createWorkspace + _reserve_vmid_and_row.
# Wrap step-0 capacity guard and step-1 reservation in ONE critical section.
self._create_lock = asyncio.Lock()   # in __init__ (process-wide create serializer)

async def createWorkspace(self, payload):
    async with self._create_lock:                                  # NEW: serialize check+reserve
        if await self.compute.getNodeMemory(payload.node) > self.settings.capacity_threshold:
            raise CapacityError(payload.node)
        ws = await self._reserve_vmid_and_row(payload)             # partial-unique INSERT (existing)
    vmid = ws.vmid                                                 # clone/boot continue OUTSIDE the lock
    # ... unchanged saga steps 2..7 ...
```

> The lock spans ONLY the read+reserve, not the multi-second clone, so concurrent creates still parallelize their slow work — they just can't both pass the capacity gate against a stale read. For `--workers >1`, replace the in-process lock with a `BEGIN IMMEDIATE` transaction that re-reads capacity inside the write transaction (Claude's discretion per CONTEXT).

### Deterministic capacity-race test (hermetic, no real clock)

```python
# Source: this repo's test patterns (FakeComputeProvider + real temp SQLite).
async def test_concurrent_creates_cannot_both_overcommit(service_with_high_mem):
    # Fake node_memory just under threshold; a SECOND running workspace would push
    # it over. Drive two createWorkspace coroutines concurrently with asyncio.gather.
    results = await asyncio.gather(
        service.createWorkspace(payload_a),
        service.createWorkspace(payload_b),
        return_exceptions=True,
    )
    # Exactly one succeeds; the other raises CapacityError (the lock serialized the gate).
    successes = [r for r in results if not isinstance(r, Exception)]
    capacity_errors = [r for r in results if isinstance(r, CapacityError)]
    assert len(successes) == 1 and len(capacity_errors) == 1
```

> To make the race deterministic, the Fake's `getNodeMemory` returns a value that flips above-threshold once one workspace exists (a small `FakeComputeProvider` subclass or a memory function that counts `_containers`). The point: WITHOUT the lock both pass; WITH it, exactly one does.

### Reaper single-pass test (inject orphan + stale creating)

```python
# Source: FakeComputeProvider exposes _containers; inject an orphan directly.
async def test_reap_destroys_orphan_and_times_out_creating(fake_compute, sqlite_db, settings):
    fake_compute._containers[250] = _FakeContainer(vmid=250, name="orphan", node="pve1")  # no DB row
    stale = await sqlite_db.createWorkspace(_ws_data("stuck", 251, status="creating"))     # old creating
    recon = Reconciler(fake_compute, sqlite_db, settings,
                       now=lambda: _parse(stale.created_at) + timedelta(seconds=999))      # past timeout
    await recon.reconcile_once()
    assert 250 not in fake_compute._containers                         # orphan reaped
    assert (await sqlite_db.getWorkspace(stale.id)).status == "error"  # creating → error
    assert 251 not in fake_compute._containers                         # its CT destroyed
```

### `EVENT_BADGE` map (UI, mirrors `status.ts`)

```typescript
// Source: 04-UI-SPEC "Event type → badge color map" (binding) + ui/src/lib/status.ts pattern.
export const EVENT_BADGE: Record<string, { token: string; label: string }> = {
  "workspace.created":      { token: "var(--ok)",         label: "Created" },
  "workspace.started":      { token: "var(--ok)",         label: "Started" },
  "workspace.stopped":      { token: "var(--text-muted)", label: "Stopped" }, // reason:idle → special-cased
  "workspace.destroyed":    { token: "var(--err)",        label: "Destroyed" },
  "terminal.connected":     { token: "var(--accent-line)",label: "Terminal connected" },
  "terminal.disconnected":  { token: "var(--text-muted)", label: "Terminal disconnected" },
  "boot.error":             { token: "var(--err)",        label: "Boot error" },      // emphasized row
  "bootconfig.persisted":   { token: "var(--text-sub)",   label: "Boot config persisted" },
};
// reaper.* → match prefix → { token: "var(--warn)", label: `Reaper · ${suffix}` }
// unknown  → { token: "var(--text-sub)", label: <raw type in mono> }  (forward-compatible)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup"/"shutdown")` | `lifespan` async context manager | FastAPI ≥ 0.93 (2023); `on_event` deprecated | Use `lifespan` for the reconciler task. `[CITED: fastapi.tiangolo.com/advanced/events]` |
| Long-lived signing keys in CI secrets | cosign **keyless** via Sigstore + GitHub OIDC | Sigstore GA (2022+), now the default recommendation | No key to rotate/leak; ci-cd §5.4 mandates it. `[CITED: sigstore/cosign]` |
| Manual in-toto provenance | `actions/attest-build-provenance` (GitHub-native, SLSA) | 2024; default-on for public repos through 2025-26 | One action emits + signs SLSA provenance bound to the digest. `[CITED: actions/attest-build-provenance]` |
| Single Trivy run for scan + report | Two-run (gate + SARIF) pattern | Ongoing trivy-action limitation (#309 open) | Required to both fail on HIGH/CRITICAL AND upload a complete SARIF. `[CITED: aquasecurity/trivy-action#309]` |
| `verify_ssl=False` (tech-spec §6.1 snippet) | CA-pinned `verify_ssl=<ca_path>` | Already corrected in `proxmoxProvider.py` | Not a Phase-4 change, but the reaper must not regress it (it goes through the seam, adding no Proxmox call). |

**Deprecated/outdated:**
- The tech-spec §6.1 `verify_ssl=False` and §6.2 `CAPACITY_GUARD_THRESHOLD` module constant are spec happy-path; the shipped code uses CA-pinned TLS and a `Settings.capacity_threshold`. Follow the SHIPPED code, not the spec snippet (per CLAUDE.md "most recent doc wins" and the SC-corrections discipline).
- The tech-spec §521 event-type comment lists the BARE shorthand (`workspace.created|started|...`); the SHIPPED events are namespaced (`workspace.created`, `terminal.connected`, `bootconfig.persisted`, and Phase-4's new `reaper.*`). The drawer badge map MUST key off the real namespaced strings (04-UI-SPEC §"use the real backend event-type strings").

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A process-level `asyncio.Lock` is sufficient for the capacity-race fix because v1 self-host runs `uvicorn --workers 1` | Pattern 5 / Pitfall 5 | If deployed with `--workers >1`, the per-process lock won't serialize across workers — need `BEGIN IMMEDIATE`. CONTEXT allows either; document the caveat. Confirm the v1 deploy uses 1 worker. |
| A2 | Row-less orphan reaps log to structured logs (not the events table) because the events FK requires a live `workspaceId` | Pitfall 3 / Open Q1 | If the planner wants orphan reaps visible in a UI/audit surface, a workspace-less event sink (or a dedicated "system" pseudo-row) is needed. Decide the audit sink. |
| A3 | `stopWorkspace` can carry a `reason: idle` into the `workspace.stopped` event `data` (via a new optional param or a reconciler-side log) | Pattern 3 / Open Q2 | The UI badge keys on `data.reason === "idle"`; if the reason never reaches `data`, the "Auto-stopped (idle)" label/amber dot never renders. |
| A4 | The Fake's `usedVmids()` returns ALL containers (not pool-scoped), so the reaper MUST re-assert the pool bound itself | Pattern 2 | Verified: `FakeComputeProvider.usedVmids` returns `set(self._containers.keys())` unfiltered; the Proxmox impl IS pool-scoped. The reaper's explicit `if vmid in pool` bound covers both. (Low risk — verified in code.) |
| A5 | GitHub Actions versions (build-push, login, metadata, setup-buildx, trivy, sbom, cosign, attest) resolve to current stable releases the planner pins by SHA | Standard Stack | A stale/wrong SHA fails CI loudly (not silently). Pin at plan-write time + verify each repo; trailing version comment per repo convention. |
| A6 | `python:3.12-slim` is the chosen `burrow-api` runtime base (vs distroless) per ci-cd §9 Open Q1 "start slim" | Standard Stack / Pitfall 8 | Distroless would change the HEALTHCHECK approach (no shell). Slim keeps `python -c` health probe simple. Confirm at plan time. |
| A7 | The reaper uses `settings.default_node` for orphan destroy when the orphan has no row (no node to read) | Pattern 2 | Multi-node is out of scope for v1 (operator picks one node), so a single default node is correct for v1. If multi-node ever lands, the orphan's node must be discovered from compute. |

## Open Questions

1. **Audit sink for row-less orphan reaps.**
   - What we know: timed-out `creating` rows and idle auto-stops have a live `workspaceId` → log normal events. A truly orphaned CT (leaked VMID, no live row) cannot satisfy the events FK.
   - What's unclear: whether row-less reaper actions should go to structured logs only, or to a dedicated audit surface.
   - Recommendation: structured `logger.info("reaper.destroyed", extra={"vmid": ...})` (redacted via `_safe`) for row-less actions; per-workspace `reaper.*` events only where a row exists. The drawer correctly never shows row-less reaps (no workspace to open). Confirm at plan time.

2. **Threading `reason: idle` into `workspace.stopped`.**
   - What we know: `stopWorkspace` currently logs `workspace.stopped` with `{}`. The UI badge map needs `data.reason === "idle"` to render "Auto-stopped (idle)".
   - What's unclear: add an optional `reason` param to `stopWorkspace`, or have the reconciler emit the reason event itself after calling stop.
   - Recommendation: add `stopWorkspace(workspace_id, *, reason: str | None = None)` and put `reason` into the event `data` when set. Operator-initiated stops pass no reason (label "Stopped"); auto-stop passes `"idle"`. Cleanest single source.

3. **`--workers` count for the v1 self-host deploy.**
   - What we know: the create lock is per-process; the VMID INSERT is cross-process; the capacity read is the unserialized gap.
   - What's unclear: whether v1 ships `--workers 1` (lock suffices) or more (needs `BEGIN IMMEDIATE`).
   - Recommendation: assume `--workers 1` for v1 (single self-host operator), implement the `asyncio.Lock`, and document the `>1` upgrade path. Confirm the deploy topology.

4. **Trivy on the `ui` (nginx) image vs the `api` image — same gate?**
   - What we know: both images are scanned (ci-cd §2.4 matrix).
   - Recommendation: run the two-run Trivy on BOTH in a matrix; the nginx-alpine base typically has fewer findings but the gate is identical (fail HIGH/CRITICAL).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker / Buildx | Image build + Trivy + container smoke (CI) | ✓ in GitHub Actions runners | ubuntu-latest ships Docker | Local Windows dev host has no Docker (per STATE.md 02-06) → compose/build validated by first CI run, not locally |
| GHCR (ghcr.io) | release.yml push | ✓ (project's own registry via `GITHUB_TOKEN`) | — | None needed — it is the target, not a dependency to install |
| GitHub OIDC provider | cosign keyless + provenance | ✓ (built into Actions) | — | None — `id-token: write` enables it |
| shellcheck | (existing, unchanged) | ✓ on ubuntu-latest | preinstalled | — |
| Real Proxmox node | Reaper/auto-stop/capacity TRUE acceptance | ✗ (by design) | — | **Fake provider in CI** is the hermetic substrate; real acceptance is the dev-homelab smoke |
| Python 3.12 / uv | api build + tests | ✓ | 3.12 | — |
| Node 22 / npm | ui build + tests | ✓ | 22 | — |

**Missing dependencies with no fallback:** none that block CI. (Real Proxmox is intentionally absent; CI proves over the Fake.)
**Missing dependencies with fallback:** Docker on the local Windows dev host (the supply-chain + image work is CI-verified on first run, consistent with the project's established "Docker not on this host → validated by CI" pattern from Plan 02-06).

## Validation Architecture

> `workflow.nyquist_validation: true` and `security_enforcement: true` (ASVS L1, block_on=high) — both sections included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework (api) | `pytest` 9.0.3 + `pytest-asyncio` 1.4.0 (`asyncio_mode=auto`) `[VERIFIED: api/pyproject.toml]` |
| Framework (ui) | `vitest` (Tier 1/2) + `@playwright/test` (Tier 3) `[VERIFIED: ui/playwright.config.ts]` |
| Config file (api) | `api/pyproject.toml` `[tool.pytest.ini_options]` |
| Config file (ui) | `ui/vitest.config.*` + `ui/playwright.config.ts` |
| Quick run (api) | `uv run pytest tests/unit/test_reconciler.py -q` (working-directory: api) |
| Quick run (ui) | `npx vitest run src/components/ActivityDrawer.test.tsx` |
| Full suite (api) | `uv run pytest -q` |
| Full suite (ui) | `npx vitest run` + `npx playwright test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAP-03 | Orphan pool CT (no live row) is destroyed; out-of-pool CT untouched | unit (Fake) | `uv run pytest tests/unit/test_reconciler.py::test_reap_destroys_orphan -x` | ❌ Wave 0 |
| CAP-03 | Timed-out `creating` row → CT destroyed + status=error | unit (Fake) | `...::test_reap_times_out_creating -x` | ❌ Wave 0 |
| CAP-03 | A `creating` row younger than the timeout is NOT swept (Pitfall 1) | unit (Fake) | `...::test_reap_spares_fresh_creating -x` | ❌ Wave 0 |
| CAP-02 | Running ws idle past window (last event = disconnect) → stopped{idle} | unit (Fake) | `...::test_auto_stop_idle -x` | ❌ Wave 0 |
| CAP-02 | connect→disconnect→connect within window → NOT stopped (Pitfall 2) | unit (Fake) | `...::test_reconnect_within_window_spares -x` | ❌ Wave 0 |
| CAP-01 (atomic) | Two concurrent creates: exactly one passes capacity, one CapacityError (Pitfall 5) | integration (real SQLite + Fake) | `uv run pytest tests/integration/test_capacity_race.py -x` | ❌ Wave 0 |
| (lifespan) | Reconcile task starts on startup + cancels cleanly on shutdown (Pitfall 4) | integration (ASGI) | `uv run pytest tests/integration/test_lifespan.py -x` | ❌ Wave 0 |
| UI-06 | Drawer reverses oldest-first → newest-first; badge map keys real types; boot.error emphasized | unit (vitest) | `npx vitest run src/components/ActivityDrawer.test.tsx` | ❌ Wave 0 |
| UI-06 | Poll only while open (enabled flag); Esc closes; focus returns to trigger | unit (vitest) | same file | ❌ Wave 0 |
| UI-06 | End-to-end: open drawer over Fake, see live event rows, close | e2e (Playwright) | `npx playwright test tests/e2e/activity-drawer.spec.ts` | ❌ Wave 0 |
| CICD-04 | Both images build; Trivy fails on HIGH/CRITICAL; SARIF uploaded | CI job (first-run authority) | `ci.yml` build-scan job | ❌ Wave 0 (workflow) |
| CICD-05 | release.yml emits SBOM (both formats) + cosign sig + provenance + GHCR push | CI job (tag-triggered) | `release.yml` publish job | ❌ Wave 0 (workflow) |

### Sampling Rate
- **Per task commit:** the quick run for the file touched (e.g. `pytest tests/unit/test_reconciler.py -q`).
- **Per wave merge:** `uv run pytest -q` (full api) + `npx vitest run` (full ui).
- **Phase gate:** full api + ui suites + `npx playwright test` green; the two new workflows' first CI run green (build/scan CI-provable; release.yml provable by a test tag against GHCR).

### Wave 0 Gaps
- [ ] `api/tests/unit/test_reconciler.py` — covers CAP-02 (idle + reconnect-spare) and CAP-03 (orphan + creating-timeout + fresh-spare). Needs a `Reconciler` fixture wired to `fake_compute` + `sqlite_db` + a settings stub with the three new keys + an injectable `now`.
- [ ] `api/tests/integration/test_capacity_race.py` — covers the atomic capacity fix; needs a Fake whose `getNodeMemory` flips above threshold once one workspace exists, driven by `asyncio.gather` of two creates.
- [ ] `api/tests/integration/test_lifespan.py` (optional but recommended) — covers clean task start/cancel via the ASGI lifespan.
- [ ] `ui/src/components/ActivityDrawer.test.tsx` + `useWorkspaceEvents` MSW handler — covers reverse/badge/emphasis/poll-gating/a11y.
- [ ] `ui/tests/e2e/activity-drawer.spec.ts` — extends the existing Playwright harness (Fake + stub ttyd already wired in `playwright.config.ts`).
- [ ] Settings keys `reconciler_period_s`, `creating_timeout_s`, `idle_window_s` in `config.py` (no test framework install needed — pytest/vitest/playwright all already present).
- [ ] CI: extend `ci.yml` static-gates DAG with the new reconciler+capacity pytest paths (mirror the existing `pytest tests/boot ...` step), and add the `build-scan` job; add `release.yml`.

*Framework install: none — `pytest`, `pytest-asyncio`, `vitest`, `@playwright/test` are all already in the repo.*

## Security Domain

> `security_enforcement: true`, ASVS L1, `security_block_on: high`. v1 is LAN-only no-auth BY DESIGN (Pitfall 12) — do not add auth assumptions.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | v1 LAN-only no-auth by design (REQUIREMENTS Out-of-Scope); do NOT add auth to v1 paths |
| V3 Session Management | no | no sessions in v1 |
| V4 Access Control | partial | the reaper's **safety bound** (only destroy in-pool, row-less VMIDs) is an authorization-of-action control — it must never act outside the worker pool |
| V5 Input Validation | yes | the drawer renders ONLY server-redacted `data` and must never re-expand/un-redact (04-UI-SPEC §Security); reconciler reads typed DTOs, no string-built SQL |
| V6 Cryptography | yes | image **signing** = cosign keyless (Sigstore), never a hand-rolled key; TLS to Proxmox stays CA-pinned (reaper adds no new Proxmox call) |
| V7 Error/Logging | yes | `reaper.*` and `boot.error` events run through `_safe()` (redacts git/CI tokens, URL userinfo, long opaque tokens, caps length) — no secret/topology in any event or log |
| V10 Malicious Code / Supply Chain | yes | SHA-pinned actions, least-priv per-job tokens, Trivy gate, SBOM, provenance attestation — the entire CICD-04/05 surface IS this control family |
| V12 Files/Resources | yes | non-root container user, read-only root FS where possible, minimal build context via `.dockerignore` (excludes `.env*`, `.git`, tests) |

### Known Threat Patterns for {FastAPI asyncio reconciler + GitHub Actions supply chain}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reaper destroys an out-of-pool / live CT (over-broad action) | Tampering / DoS | Safety bound: VMID must be in pool range AND absent from live DB rows; reuse idempotent `destroyCt`; deterministic single-pass test asserts an out-of-pool CT is untouched |
| Secret/topology leaks into a `reaper.*` event or log | Information Disclosure | Route all event/log text through the existing `_safe()`; `reaper.*` events carry only redacted, bounded reason strings |
| Auto-stop wrongly kills an active session (accidental drop) | DoS | Idle requires the LAST terminal event to be a disconnect older than the window (Pitfall 2); reconnect re-arms |
| Compromised/typosquatted GitHub Action runs in CI | Tampering / Elevation | All third-party actions SHA-pinned (Pitfall 14 / ci-cd §5.5); workflow default `contents: read`; publish job widens only the exact perms it needs |
| Long-lived signing key leaks from CI secrets | Information Disclosure / Spoofing | cosign **keyless** (no stored key); ephemeral OIDC cert via Fulcio, recorded in Rekor |
| Unsigned/unscanned image reaches GHCR | Spoofing / Tampering | Fail-closed DAG: scan gate before publish; every published image signed + SBOM'd + provenance-attested by digest |
| Build context leaks `.env`/secrets into an image layer | Information Disclosure | `.dockerignore` excludes `.env*`, `.git`, tests, local state (ci-cd §2.2); non-root runtime; Trivy/Dockle misconfig scan |
| Image runs as root → container escape blast radius | Elevation of Privilege | Non-root `USER`, read-only root FS, drop unneeded capabilities (ci-cd §2.2) |

## Project Constraints (from CLAUDE.md)

The planner MUST honor these (same authority as locked decisions):

- **SPDX two-line header on every new source file** (AGPL-3.0-or-later) — `reconciler.py`, `ActivityDrawer.tsx`, `useWorkspaceEvents.ts`, `events.ts`, Dockerfiles, `release.yml`, all test files.
- **Provider seams stay abstract.** The reaper depends ONLY on `ComputeProvider` + `DbProvider` ABCs — no `proxmoxer`/`aiosqlite` import (the seam-leakage tokenize guard will fail the build otherwise).
- **snake_case DB columns → camelCase JSON** via `CamelModel`; the drawer's `WorkspaceEvent` TS type mirrors the camelCase JSON.
- **Structured JSON logging** with secret/topology redaction (`_safe()` precedent) for all `reaper.*` log lines.
- **Security headers on API responses** — unchanged (no new route; the drawer reuses the existing events endpoint).
- **Tests with every change**; every bug fix lands a failing-first regression test in the right tier.
- **No secrets / no deployment topology in the repo** — the three new Settings keys are non-secret with placeholder defaults; GHCR auth is the built-in `GITHUB_TOKEN`; cosign is keyless (no stored key).
- **MVP mode / vertical slices** — the runtime-hardening, drawer, and supply-chain halves are independent slices the planner can wave separately.
- **Conventional Commits**; PR title is itself a valid Conventional Commit (squash-merge).
- **ADR for any baseline deviation** — e.g. the in-process-reconciler choice and the capacity-lock-vs-transaction decision may warrant a short ADR per the repo's ADR-per-phase discipline (Phase 0 and 3 each authored ADRs); confirm with the user whether Phase 4 needs one for the reconciler architecture.

## Sources

### Primary (HIGH confidence)
- This repo (verified by direct read): `api/services/workspaceService.py` (`_compensate`, `_safe`, `_reserve_vmid_and_row`, `_db_used_vmids`, create saga), `api/compute/{provider,fakeProvider,proxmoxProvider}.py` (`usedVmids`, idempotent `destroyCt`, pool-scoping), `api/db/{provider,sqliteProvider}.py` (`getEvents` oldest-first, WAL+busy_timeout, partial-unique INSERT), `api/routers/{workspaces,terminal}.py` (events endpoint, `terminal.connected/disconnected`), `api/main.py` (no lifespan yet — attach point), `api/config.py`, `ui/src/{api/client.ts,hooks/useWorkspaces.ts,lib/status.ts,types/workspace.ts,components/TerminalPanel.tsx}`, `ui/playwright.config.ts`, `.github/workflows/ci.yml`, `api/pyproject.toml`.
- `docs/ci-cd-and-testing.md` §2 (image strategy), §3 (DAG), §4 (test tiers), §5 (supply-chain) — authoritative for CICD-04/05.
- `.planning/phases/04-hardening-release/04-CONTEXT.md` + `04-UI-SPEC.md` (locked decisions + binding drawer contract).
- `docs/tech-spec.md` §5.3 (state machine), §5.x event types, §6 (capacity).
- FastAPI lifespan docs — `[CITED: fastapi.tiangolo.com/advanced/events]`.

### Secondary (MEDIUM confidence)
- `actions/attest-build-provenance` README (subject-name/digest, push-to-registry, `attestations: write`) — `[CITED: github.com/actions/attest-build-provenance]`.
- `sigstore/cosign` + cosign-installer (keyless OIDC, `id-token: write`) — `[CITED: github.com/sigstore/cosign]`.
- `anchore/sbom-action` / syft (SPDX + CycloneDX; syft 1.42, Feb 2026) — `[CITED: github.com/anchore/sbom-action; anchore/syft]`.
- `aquasecurity/trivy-action` SARIF/exit-code conflict + two-run workaround — `[CITED: github.com/aquasecurity/trivy-action#309, #273]`.

### Tertiary (LOW confidence — flagged for validation)
- Exact current SHAs/versions of each GitHub Action (build-push, login, metadata, setup-buildx, trivy, sbom, cosign-installer, attest) — `[ASSUMED]`; pin + verify at plan-write time per the repo's SHA-pin convention.

## Metadata

**Confidence breakdown:**
- Runtime-hardening (reaper/auto-stop/capacity): HIGH — every seam the design uses is verified in the repo by direct read; the algorithms are pure functions of existing state; the hermetic test substrate (Fake + temp SQLite + injected `now`) is already proven by Phases 1–3.
- Drawer (UI-06): HIGH — fully specified in 04-UI-SPEC; reuses the verified `useWorkspaces` + `status.ts` patterns; the only residual is threading `reason: idle` (Open Q2).
- Supply chain (CICD-04/05): HIGH on the pattern (ci-cd spec is authoritative + tooling confirmed), MEDIUM on exact action SHAs/versions (pin at plan time).
- Pitfalls: HIGH — drawn from verified code behavior (FK, pool-scoping, idempotent destroy) and confirmed external issues (Trivy #309).

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 for the codebase-grounded findings (stable); 2026-06-18 for the GitHub Actions versions (fast-moving — re-verify SHAs at plan-write time).

## RESEARCH COMPLETE

**Phase:** 4 - Hardening & Release
**Confidence:** HIGH

### Key Findings
- The runtime-hardening half is pure assembly of EXISTING seams: `compute.usedVmids()` (pool-scoped in Proxmox, all-containers in Fake → reaper re-asserts the bound), idempotent `destroyCt` (no new compute method), `getEvents` (oldest-first, drives idle detection), `WorkspaceService.stopWorkspace` (guarded auto-stop), and `_safe()` (event redaction). The only NEW backend code is `Reconciler.reconcile_once()` + a FastAPI `lifespan` (main.py has none yet).
- Testability hinges on an **injectable `now`** + a **single `reconcile_once()` pass** over the Fake — zero real clock, zero Proxmox, zero new test deps (reject `freezegun`/`time-machine`). The capacity race is made deterministic with a Fake whose `getNodeMemory` flips above threshold once one workspace exists.
- The capacity-race fix is a **one-block edit**: wrap the existing step-0 capacity guard + step-1 reservation in a single `asyncio.Lock` (KISS for `--workers 1` v1) — the VMID INSERT is already race-safe; only the capacity READ was the unserialized gap.
- Two confirmed supply-chain gotchas: **Trivy needs TWO runs** (gate on HIGH/CRITICAL via table+exit-code; full SARIF via a second `if: always()` run) because SARIF ignores the severity-scoped exit-code (#309); and the publish job needs exactly `packages: write + id-token: write + attestations: write` or keyless cosign/provenance fail silently.
- **No new runtime PyPI/npm dependency** in the entire phase; the CI additions are SHA-pinned GitHub Actions governed by the existing repo convention.

### File Created
`E:\repos\burrow\.planning\phases\04-hardening-release\04-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All runtime deps already in-repo (verified by read); CI tooling confirmed against official sources; zero new registry packages |
| Architecture | HIGH | Reconciler/lifespan/capacity patterns map onto verified existing seams; supply-chain follows the authoritative ci-cd spec verbatim |
| Pitfalls | HIGH | Grounded in verified code (events FK, pool-scoping, idempotent destroy) and a confirmed external issue (Trivy #309) |

### Open Questions (carried for the planner / discuss-phase)
1. Audit sink for **row-less orphan reaps** (events FK needs a live workspaceId) → recommend structured logs for row-less, per-workspace events otherwise.
2. Thread **`reason: idle`** into `workspace.stopped` (the UI badge keys on it) → recommend an optional `reason` param on `stopWorkspace`.
3. v1 **`--workers` count** (per-process lock vs `BEGIN IMMEDIATE`) → recommend assume `--workers 1`, document the `>1` path.
4. Whether the reconciler-architecture + capacity-lock choice warrants an **ADR** (repo authored ADRs in Phases 0 and 3).

### Ready for Planning
Research complete. The planner can create PLAN.md files for three independent vertical slices (runtime-hardening, activity drawer, supply-chain release), all CI-verifiable over the Fake provider / GitHub Actions, with the four open questions surfaced for user confirmation where they become locked decisions.
