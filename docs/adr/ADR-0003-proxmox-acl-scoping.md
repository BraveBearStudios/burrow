<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0003: Proxmox ACL scoping — pool/storage/node, not cluster-wide `/vms`

## Status

Accepted

## Context

Burrow's control plane authenticates to Proxmox with a least-privilege
`BurrowProvisioner` role (the verified 9-privilege set:
`VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt
Datastore.AllocateSpace Datastore.Audit Sys.Audit`, plus conditional `SDN.Use`) on a
`privsep=1` API token. Getting the privilege *list* right is only half of least
privilege — the other half is **where** the role is granted (PROXMOX-PRIMING §2.2).

Granting the role at `/` works but is over-broad: a leaked token could touch every
guest, datastore, and node in the cluster. Two scoping models were considered:

- **`/pool/burrow-workers` + `/storage/<rootfs>` + `/nodes/<node>` (tight, chosen)** —
  fences Burrow to its own pool, one storage, and the scheduling node(s) only.
- **`/vms` cluster-wide (broad, fallback)** — simpler, but every guest in the cluster
  is in blast radius.

A privsep nuance compounds the scoping choice: with `--privsep 1` (the default for new
tokens) a token's effective rights are the **intersection of the user's and the
token's** ACLs. The role must be granted to **both** the user and the token at **every**
path, or the token authenticates but every clone returns 403.

## Decision

Grant the `BurrowProvisioner` role with **tight, path-scoped ACLs**, to **both** the
`burrow@pve` user and the `burrow@pve!burrow` token at every path:

| Privilege subset | Granted at | Caps blast radius to |
|---|---|---|
| `VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt` | `/pool/burrow-workers` | Burrow's own CTs only |
| `VM.Clone VM.Audit` | `/vms/<template-vmid>` | the golden template as clone source |
| `Datastore.AllocateSpace Datastore.Audit` | `/storage/<rootfs-storage>` | one storage pool |
| `Sys.Audit` | `/nodes/<node>` (per scheduling node) | per-node status reads only |
| `SDN.Use` (if SDN enforcement is on) | the `<bridge>` / vNet | the one bridge |

- The resource pool `burrow-workers` is the fence: a token leak cannot reach unrelated
  production guests.
- **Consequence on the clone path:** because the ACL is scoped to
  `/pool/burrow-workers`, each newly cloned worker VMID **must be added to the pool**
  (e.g. `pvesh set /pools/burrow-workers -vms <id>`), or the whole worker VMID range
  pre-added, so the scoped token retains rights over the clone it just created. This
  obligation lives in `ProxmoxComputeProvider.clone` (Phase 1).
- `GET /cluster/nextid` needs no grant (works for any authenticated token) but Burrow
  does not use it for allocation — it is neither race-safe nor range-bounded.

All topology values (`<rootfs-storage>`, `<node>`, `<template-vmid>`, `<bridge>`) are
placeholders; the operator fills their own LAN values into the gitignored `.env` and
the `30-network-notes.md` record. The token value is captured into `.env` only — never
committed, logged, echoed, or passed as a CLI argument.

The **`/vms` cluster-wide** grant is recorded as an explicit, acceptable **fallback**
for a disposable LAN-only token, with the same both-principals (user ∩ token) rule.

## Consequences

- A leaked token's blast radius is fenced to Burrow's pool, one storage, and the
  scheduling node(s) — a genuine least-privilege boundary rather than cluster-wide
  reach.
- The clone path gains a pool-membership step (`ProxmoxComputeProvider.clone` must add
  each new VMID to `burrow-workers`). This is a real surface change versus the broad
  `/vms` model, which needs no such step.
- Both the user and the token must be granted the role at every path (privsep
  intersection); forgetting the token grant is the most common "authenticates but every
  clone 403s" failure, so it is called out in the host-prime kit.
- Per-node `Sys.Audit` means adding a scheduling node requires granting the node path;
  this is an intentional cost of node-scoped reads (no cluster/HA/Corosync exposure).

## Revisit trigger

Adoption of Proxmox SDN with permission enforcement (adds the `<bridge>` grant as
mandatory), a multi-node scheduling expansion that makes per-node grants burdensome, or
a decision to widen to `/vms` for operational simplicity (explicitly trading blast
radius for fewer ACL paths).
