<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0007: ttyd binds the worker LAN interface, not `lo` (WORK-04)

## Status

Accepted

## Context

The tech-spec contradicts itself on where the worker's ttyd listens. The boot snippet
(spec §9.3) binds ttyd to the loopback interface (`lo`), while the WS-proxy design
(spec §6.4) has the control plane dial the worker's ttyd at `ws://<lxcIp>:7681/ws` over
the worker's **network** address (SC-9, WORK-04).

These cannot both be true. ttyd bound to `lo` only accepts connections originating
**inside** the worker container; a remote connection from the control plane is refused.
The control plane and the worker are **separate hosts** on the LAN (the worker is an
ephemeral LXC; the control plane is its own persistent box), so the proxy must reach
ttyd over the worker's LAN address — exactly the address ADR-0004 derives from the VMID.
A `lo`-bound ttyd makes WORK-04 ("ttyd reachable by the control-plane proxy over the
worker network address") impossible.

This is a security-relevant binding decision, so it carries an explicit security
dimension rather than being a silent default.

## Decision

Bind ttyd to the worker's **LAN interface** (its VMID-derived static address), **not**
`lo`, in `burrow-boot.sh`.

- The control-plane WS proxy can then reach `ws://<lxcIp>:7681/ws` over the worker's LAN
  address, satisfying WORK-04 / SC-9 and resolving the spec §9.3 ↔ §6.4 contradiction in
  favor of the §6.4 proxy design.
- The binding is frozen in Phase 0 (it shapes the golden template's boot script);
  real-world acceptance (ttyd reachable on the LAN interface from the proxy) is a
  dev-homelab smoke item, deferred.

### Security dimension

- Binding to the LAN interface widens ttyd's exposure from "container-internal only" to
  "anything on the worker LAN can reach `:7681`." Under Burrow's **v1 LAN-only, no-auth
  posture** (CLAUDE.md), this LAN boundary is the **accepted** trust boundary: the LAN is
  treated as trusted in v1, and ttyd has no authentication of its own.
- **Worker `:7681` must never be exposed beyond the LAN.** No port-forward, no public
  bind, no exposure past the LAN edge. The control-plane nginx/proxy binds the LAN
  interface only (never `0.0.0.0` on a multi-homed host).
- If the Proxmox firewall is later enabled, control-plane → worker `:7681` needs an
  explicit allow rule (it is open by default); enabling the firewall and adding that
  rule are a single deliberate change.
- Authentication / network isolation for ttyd is a **hosted-path** concern, out of scope
  for v1 — recorded here as the boundary the hosted path must tighten.

## Consequences

- WORK-04 is satisfiable: the proxy reaches ttyd over the worker LAN address; the
  five-step create→live→stop→start→destroy smoke test can exercise the real terminal
  path.
- ttyd's `:7681` is reachable by any host on the worker LAN, with no ttyd-level auth.
  This is acceptable **only** under the v1 LAN-only posture and is the explicit security
  trade recorded here.
- Network topology must keep workers on a trusted LAN segment and must never route or
  forward `:7681` outward; nginx/proxy LAN-only binding is a hard requirement.
- The hosted/multi-tenant path inherits an obligation to add authentication and/or
  network isolation in front of ttyd before relaxing the LAN-only assumption.

## Revisit trigger

Any move off the v1 LAN-only, no-auth posture: a hosted or multi-tenant deployment,
exposing Burrow beyond a trusted LAN, or a requirement to authenticate/isolate worker
terminal access. Enabling the Proxmox firewall is a related operational trigger (add the
`:7681` allow in the same change).
