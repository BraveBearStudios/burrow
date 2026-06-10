<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0004: Static IP derived from VMID

## Status

Accepted

## Context

A worker's IP address must be known to the control plane so the WS terminal proxy can
reach ttyd and so the worker can be addressed for its lifecycle. Two approaches exist:
DHCP plus a Proxmox API poll to discover the leased address, or computing a static IP
from the worker's VMID.

DHCP discovery is unreliable for Burrow's workers (SC-6, PROXMOX-PRIMING §4):

- Workers are **unprivileged LXC** containers. They have **no QEMU guest agent** (that
  is a VM-only facility), so the agent-based interface query that VMs offer does not
  exist for containers — this is precisely *why* a static scheme is the design, not an
  afterthought.
- The container interfaces API is unreliable for reading a DHCP lease, so a poll
  introduces a race: the control plane does not know the address the instant the VMID
  is allocated, and must retry against an unreliable source.

Burrow already allocates VMIDs from a bounded pool `[<pool-start>, <pool-end>]` under a
DB unique reservation (SC-3). If the IP is a pure function of the VMID, the address is
known the instant the VMID is reserved — no polling, no race — and a VMID collision is
*the same event* as an IP collision, so the single DB unique constraint on `vmid`
guards both.

## Decision

**Compute the worker's static IP from its VMID** rather than discovering it via DHCP.

- The operator records the concrete formula for their LAN in
  `cc-worker-config/lxc/host-prime/30-network-notes.md` (placeholders only in the repo).
  The scheme maps `VMID → <subnet>.<last-octet>` within the worker pool — e.g. on a
  `/24` LAN, worker `2NN` → `<subnet>.2NN/24`, gateway `<gw>`, bridge `<bridge>`.
- The same `30-network-notes.md` is the single source of truth for **both** the
  per-clone `pct set net0` (applied at clone time inside the create saga) **and** the
  control plane's IP computation, so the two can never drift.
- **Off-host DHCP exclusion is mandatory and load-bearing.** The worker IP range MUST
  be reserved out of the LAN DHCP server's pool (router / pfSense / dnsmasq — an
  off-host action, no Proxmox command). If DHCP can hand out a worker IP, a worker boot
  causes a LAN address conflict. The template and the control plane must sit on
  addresses **outside** the worker range.
- Applied at clone time (runtime, needs `VM.Config.Network` — see ADR-0003):
  `pct set <vmid> -net0 name=eth0,bridge=<bridge>,ip=<subnet>.<oct>/<prefix>,gw=<gw>`
  (`ip=` takes CIDR; `gw=` a bare gateway IP). All values are placeholders.

## Consequences

- The worker address is deterministic and known at VMID-reservation time: no interface
  poll, no guest agent, no DHCP-lease race in the create saga.
- The DB unique constraint on `vmid` doubles as IP-collision protection, since one VMID
  maps to exactly one IP.
- A new operator obligation exists **outside** the repo and **outside** Proxmox: the
  worker IP range must be excluded from the LAN DHCP scope. This is the one collision-
  avoidance step the kit cannot perform; it is documented in `30-network-notes.md` and
  surfaced in the Day-0 runbook.
- The worker VMID pool is effectively also an IP pool; exhausting one exhausts the
  other. Pool sizing is a network-planning decision the operator records per LAN.

## Revisit trigger

A deployment where the worker subnet cannot be carved out of DHCP (forcing dynamic
addressing), workers gaining a reliable agent-based interface query, or a move to
multiple subnets / overlay networking that breaks the single `VMID → IP` formula.
