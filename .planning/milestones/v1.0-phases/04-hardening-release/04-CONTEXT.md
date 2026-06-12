<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 4: Hardening & Release - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

The fleet stays healthy unattended — orphans are reaped, idle workspaces auto-stop,
capacity holds under concurrency — and the release path produces signed, attested,
scanned images in GHCR. This phase adds: (a) an in-process periodic reconciler that
reaps orphaned Proxmox CTs / leaked VMIDs / timed-out `creating` rows and auto-stops
idle workspaces; (b) a fix that serializes the capacity check with VMID reservation so
concurrent creates cannot overcommit a node; (c) a per-workspace event-log activity
drawer in the React UI (consuming the existing `GET /api/v1/workspaces/{id}/events`);
and (d) the container/supply-chain release path (Dockerfiles, image scan, SBOM, cosign
signing, SLSA provenance, GHCR publish) per `docs/ci-cd-and-testing.md`.

In scope: reaper + auto-stop reconciler, capacity-race fix, event drawer UI, Dockerfiles
for `burrow-api` + `burrow-ui`, image scan gate, `release.yml` supply-chain path. Out of
scope: real-Proxmox acceptance of reaper/auto-stop/capacity-under-concurrency (dev-homelab
smoke only — CI is hermetic over the Fake provider); auth / public exposure (v1 is LAN-only,
no auth, Pitfall 12). The supply-chain gates (CICD-04/05) ARE fully CI-verifiable.

</domain>

<decisions>
## Implementation Decisions

### Reconciler — Reaper + Auto-stop runtime (CAP-02, CAP-03)
- A **single in-process asyncio periodic reconciler** (started/stopped via the FastAPI
  lifespan) performs BOTH reaping and idle auto-stop. No external cron/systemd timer; one
  loop, two responsibilities (KISS for the single self-host process).
- Reaper scope is all three reconciliations (SC-1/SC-11): destroy Proxmox CTs in the
  worker pool that have **no owning DB row**, free leaked VMIDs, and mark timed-out
  `creating` rows `error` (destroying their CTs). Idempotent destroy (destroy of a missing
  CT is a no-op, Pitfall 7).
- Safety bound: the reaper only ever destroys a CT whose VMID is **in the configured worker
  pool range AND has no live owning row** — it never touches out-of-pool CTs. Each action
  emits a structured `reaper.*` event (redacted, no secrets/topology).
- Intervals are configurable with defaults: reconciler period ~60s, `creating`-row timeout
  ~300s, idle auto-stop window ~30 min. (Exact values at Claude's discretion within these.)

### Auto-stop semantics + capacity concurrency (CAP-02)
- Idle = **no active terminal WebSocket connection for longer than the window while the
  workspace is `running`**, reconciled with the SC-8 detach semantics: idle is the
  *intentional* lifecycle end, NOT an accidental socket drop (a brief disconnect/reconnect
  must not trip it).
- Idle is derived from the **terminal connect/disconnect events already in the event log**
  (last disconnect timestamp + no currently-active connection) — no new schema column.
- Auto-stop action is **STOP, not destroy** — the workspace is preserved and restartable;
  it emits `workspace.stopped` with `reason: idle`, consistent with detach-not-terminate.
- Capacity-under-concurrency fix: make the **capacity check + VMID reservation atomic**
  (a single DB transaction / lock around check-then-reserve) so two concurrent creates
  cannot both pass the node-RAM check and overcommit the node. (The VMID partial-unique
  INSERT is already race-safe; the *capacity check* is the unserialized gap being closed.)

### Event Drawer UI (UI-06)
- Surface: a **right-side slide-in drawer**, opened per-workspace from the workspace
  row/panel header, showing the full event log.
- Data: **poll `GET /api/v1/workspaces/{id}/events`** via TanStack Query with a
  `refetchInterval` while the drawer is open, reusing the existing `ui/src/api/client.ts`
  + hook pattern (e.g. mirror `useWorkspaces`). No new streaming endpoint.
- Row format: **newest-first**; each row shows a timestamp, a color-coded type badge
  (`created`/`started`/`stopped`/`destroyed`/`terminal.connected`/`terminal.disconnected`/
  `boot.error`), and the redacted `data` summary; `boot.error` is visually emphasized.
- Styling honors the **design handoff** (`design/Burrow-handoff/` + `docs/design/` tokens)
  and matches the existing react-mosaic/xterm app shell.

### Images & Release supply-chain (CICD-04, CICD-05)
- Dockerfiles (per `docs/ci-cd-and-testing.md` §2.2): **multi-stage, base image pinned by
  digest** (`@sha256:…`, not a tag), **non-root** user, read-only root FS where possible,
  a `HEALTHCHECK` (`api`: `GET /health`; `ui`: nginx 200 on `/`), and OCI source/revision
  labels (AGPL §13).
- Image scan: **Trivy, fail on HIGH and CRITICAL** (no unwaived findings), results uploaded
  as **SARIF** to GitHub code scanning, run in the build job (CICD-04).
- Release path (`release.yml`, triggered on release published / tag `v*`): **syft SBOM in
  SPDX + CycloneDX**, **cosign keyless** signing by digest (Sigstore + GitHub OIDC, no
  long-lived keys), and a **SLSA build-provenance attestation**, then **push to GHCR** with
  least-privilege per-job `permissions` and third-party actions **SHA-pinned** (Pitfall 14).
- Workflow split: `ci.yml` builds + scans on PR **without pushing**; `release.yml` owns
  SBOM/sign/provenance/GHCR-publish (ci-cd §3.1). v1 stays LAN-only — no public exposure
  (Pitfall 12).

### Claude's Discretion
- Exact reconciler interval/timeout/window values within the ranges above, the precise
  drawer animation/markup, the SQL/locking mechanism for the atomic capacity check, and the
  Dockerfile layer structure are at Claude's discretion, guided by the spec and existing
  conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/services/workspaceService.py` — the create saga: capacity guard (`getNodeMemory >
  capacity_threshold`, CAP-01) at step 0, VMID reserve via DB partial-unique INSERT
  (`_reserve_vmid_and_row`), idempotent compensation. The reconciler reuses
  `compute.usedVmids()`, `_db_used_vmids()`, stop/destroy, and `logEvent`.
- `api/routers/workspaces.py` — `GET /workspaces/{id}/events` already returns the event log
  (the drawer's data source).
- `api/compute/{fakeProvider,proxmoxProvider}.py` — list/destroy CT primitives the reaper
  drives (Fake for CI, Proxmox for the homelab smoke).
- UI: `ui/src/api/client.ts`, `ui/src/hooks/useWorkspaces.ts` (TanStack Query pattern to
  mirror for `useWorkspaceEvents`), `ui/src/components/WorkspaceList.tsx` /
  `WorkspaceLayout.tsx` (where the drawer trigger lives), `ui/src/lib/status.ts` +
  `themes.ts` (badge colors / design tokens), `ui/src/types/workspace.ts`.
- `.github/workflows/ci.yml` — the existing pipeline to extend with the build+scan job
  (the static-gates job already runs reuse/shellcheck/pytest).
- `docs/ci-cd-and-testing.md` §2 (image strategy), §3 (pipeline DAG), §5 (supply-chain) —
  the authoritative spec for CICD-04/05.

### Established Patterns
- Standard envelope (`data`/`meta`/`error`), camelCase JSON ↔ snake_case DB.
- Structured JSON logging with secret/topology redaction (`_safe()` precedent).
- Provider seams (`ComputeProvider`, `DbProvider`) stay abstract — the reaper must not leak
  Proxmox/SQLite specifics past them.
- Hermetic test substrate: Fake provider + injected orphans/timeouts for the reaper;
  Playwright + Fake for the drawer e2e.

### Integration Points
- Reconciler ↔ FastAPI lifespan (start/stop the background task).
- Drawer ↔ `GET /workspaces/{id}/events` ↔ TanStack Query.
- Build/scan ↔ `ci.yml`; SBOM/sign/provenance/publish ↔ new `release.yml`.

</code_context>

<specifics>
## Specific Ideas

- `docs/ci-cd-and-testing.md` §2.2/§5 is the locked reference for CICD-04/05 (digest-pinned,
  non-root, HEALTHCHECK, Trivy HIGH/CRITICAL, syft SPDX+CycloneDX, cosign keyless, SLSA).
- Design handoff under `design/Burrow-handoff/` + `docs/design/` governs the drawer's visual
  language.
- SC-8 detach semantics (Phase 0/2) define "idle" so auto-stop is not an accidental-drop killer.

</specifics>

<deferred>
## Deferred Ideas

- Real-Proxmox acceptance of reaper / auto-stop / capacity-under-concurrency — dev-homelab
  smoke gate (the "looks done but isn't" checklist), not CI.
- harden-runner egress allowlist, vuln-waiver allowlist format/expiry policy — open items
  noted in PROJECT.md; adopt-now-vs-defer is a release-polish decision, not core to this phase.
- Auto-select worker node / multi-node capacity — out of scope (v1 operator picks the node).

</deferred>
