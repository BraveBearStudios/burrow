<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0002: Boot-config delivery is pull-at-boot, not push

## Status

Accepted

## Context

The tech-spec and the original requirements assume the control plane *injects* a
worker's boot configuration into the container before first boot — conceptually a
`pct exec` / `pct push` of `/etc/burrow/worker.env` into the new LXC (WORK-03,
SC-4/SC-5, the `injectBootConfig` step of the create saga).

Research against current (2026) Proxmox VE 8.x verified a load-bearing fact:
**`pct exec` and `pct push` are node-local CLI commands only — they are NOT exposed by
the Proxmox HTTPS REST API.** Unlike QEMU VMs (which expose
`/nodes/{node}/qemu/{vmid}/agent/exec` via the guest agent), **LXC containers have no
exec / push / file-write API surface.** `proxmoxer`, a thin HTTPS wrapper over that
API, therefore cannot write `/etc/burrow/worker.env` into a container through any
provider method (PROXMOX-PRIMING §1). The spec's push mechanism is impossible over the
channel the control plane actually speaks.

Three ways to close the gap were considered:

- **A. SSH-to-node push** — the control plane SSHes to the node as a restricted,
  forced-command key and runs `pct push`. Reintroduces a second, root-gated trust
  channel and node coupling; keeps a file-injection model that fights the seam.
- **B. Pull-at-boot (chosen)** — the worker fetches its own non-secret config from a
  new internal control-plane endpoint at boot. Pure HTTP, no node-local CLI, no second
  trust channel, keeps the `ComputeProvider` seam HTTPS-only.
- **C. API-only injection** — rejected: no API path writes an arbitrary file into a CT
  rootfs (only `net0` / static IP is API-settable), so it does not solve env injection.

This is the highest-priority Phase-0 decision because Phase 1's `injectBootConfig`
implementation and the bootconfig endpoint, and Phase 3's `burrow-boot.sh` pull step,
all build on it.

## Decision

Adopt **Option B — pull-at-boot.**

- `injectBootConfig` becomes a **DB write** (persist the per-workspace boot intent),
  not a node command. The `FakeComputeProvider` no-ops it trivially (it has no DB and
  no boot), which keeps the hermetic test substrate honest.
- The worker, knowing its own VMID from its hostname / static IP (see ADR-0004),
  fetches its configuration at boot from a new internal endpoint:
  **`GET /api/v1/internal/bootconfig/{vmid}`** → the per-workspace, **non-secret**
  identifiers the control plane already holds in SQLite (`CONFIG_REPO`,
  `CONFIG_BRANCH`, `PROJECT_REPO`, `PROJECT_BRANCH`).
- **Secrets never travel through an injected env file.** The worker requests a
  **short-lived, repo-scoped** git credential from the same endpoint at boot, uses it
  for `git clone`, and discards it. It is never written to `/etc/burrow/worker.env`.
- `burrow-boot.sh` **pulls** its config — one bounded, retried HTTP call — instead of
  receiving it. The control plane is already reachable from the worker subnet (the WS
  terminal proxy reaches the worker, and the worker reaches its config repo).

Scope of this ADR: the **decision and contract shape** are frozen here. The
`GET /api/v1/internal/bootconfig/{vmid}` endpoint implementation lands in **Phase 1**;
the `burrow-boot.sh` pull step lands in **Phase 3**.

## Consequences

- The `ComputeProvider` seam stays HTTPS-only and node-agnostic: `injectBootConfig` is
  "persist intent," with no `pct`, no SSH, and no node-local shell.
- A new internal API surface is added: `GET /api/v1/internal/bootconfig/{vmid}`. Its
  threat model (validate `vmid ∈ [pool_start, pool_end]`, non-secret payload only,
  worker authenticates by its own static IP/VMID, short-lived credential issuance) is
  flagged for the Phase-1 endpoint and is **not** in scope here.
- Secrets (git deploy tokens) stay off any worker-readable surface: short-lived,
  repo-scoped, used-and-discarded at boot — never persisted to worker env.
- Requirements that assumed push (WORK-03 / SC-4 / SC-5) are reframed around pull. The
  worker subnet must be able to reach the control plane (already true).
- Option A (restricted SSH + `pct push`) is reserved as a fallback **only** if a future
  requirement forces writing a file into the container filesystem before first boot
  that the worker cannot fetch over HTTP. If ever adopted it must SSH as `root@pam`,
  lock the key with a forced command and `restrict`, and validate the VMID is in range.

## Revisit trigger

A future requirement to place a file into a worker's rootfs *before* first boot that
the worker cannot fetch over HTTP (would reopen Option A), or Proxmox exposing a
first-class LXC exec/push API over HTTPS (would reopen direct injection).
