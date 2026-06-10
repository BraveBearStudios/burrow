<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0005: Clone workers with `--full`, not linked

## Status

Accepted

## Context

Burrow creates each worker by cloning the golden CT template. Proxmox offers two clone
modes for a template: a **linked** clone (the default for a CT *template*), which shares
the template's base image and stores only the divergence, and a **full** clone
(`--full`), which copies the rootfs so the new container is fully independent of the
template (PROXMOX-PRIMING §3.2).

Burrow's workers are **ephemeral**: created on demand and destroyed when the operator is
done, at which point their disk space should actually be freed. A linked clone couples
every running worker to the template's base image — the template cannot be changed or
removed while linked clones exist, and a linked clone's `destroy` does not cleanly
release independent space. That coupling is wrong for a fleet of throwaway workers.

The cost of `--full` depends entirely on the rootfs storage type:

- On **thin storage** (`lvmthin`, `zfspool`), a full clone is copy-on-write-thin: only
  written blocks consume space, so a full clone is **cheap** and `destroy` frees the
  worker's divergence.
- On **thick LVM**, each full clone physically reserves the entire rootfs up front —
  the trap. The worker pool must not run on thick LVM.

## Decision

Clone every worker with **`--full`** (independent clone), and run the worker rootfs pool
on **thin storage** so full clones stay cheap.

- `ProxmoxComputeProvider.clone` passes `full=1` (the `ComputeProvider.cloneCt`
  signature already carries `full: bool = True`). The `FakeComputeProvider` records the
  clone as an independent container, matching the real provider's observable effect.
- Workers are fully decoupled from the template: the template can be updated or
  re-provisioned without disturbing running workers, and a worker `destroy` frees its
  space on thin storage.
- A full clone takes longer than a linked clone. Budget that time into the **UPID
  blocking wait** (`waitTask`) of the create saga, **not** into the ttyd health-check
  timeout — conflating the two would cause spurious "ttyd not ready" failures.

## Consequences

- Workers are independent: template lifecycle (update, re-provision, eventual delete) is
  not blocked by live clones, and `destroy` actually reclaims space.
- The worker rootfs pool **must** be thin storage. Running `--full` on thick LVM
  reserves the full rootfs per clone and is explicitly rejected; the host-prime storage
  guidance and `30-network-notes.md`/PRIMING.md call this out.
- Clone latency is higher than linked. The create saga must account for it in the UPID
  wait window, keeping the ttyd health timeout independent.
- On thin storage the real limiter is RAM (the node-RAM capacity guard) long before
  disk, but an over-committed thin pool that fills is a hard outage — the operator must
  monitor thin-pool fill.

## Revisit trigger

A deployment constrained to thick storage (where `--full` is prohibitively expensive and
linked clones plus a frozen template might be reconsidered), or a future need for
long-lived (non-ephemeral) workers where template coupling is acceptable.
