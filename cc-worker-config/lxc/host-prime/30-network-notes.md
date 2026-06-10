<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# 30 — Network Notes: Static-IP-from-VMID (SETUP-05)

**This is a decision record, not a script.** The static-IP scheme is something
the operator records for *their* LAN. The repo ships placeholders only; fill in
your real values in a copy kept outside version control (or in your gitignored
`.env` for the control-plane keys).

> Source: `.planning/research/PROXMOX-PRIMING.md` §4. Decision pinned in
> `docs/adr/ADR-0004-static-ip-from-vmid.md`.

## Why static-IP-from-VMID

Unprivileged LXC has no guest agent, and the Proxmox interfaces API is
unreliable for DHCP leases. So Burrow **computes** each worker's IP from its
VMID and knows the address the instant a VMID is allocated — no polling, no
race. A VMID collision *is* an IP collision, so the DB unique constraint on
`vmid` guards both at once.

## The scheme (placeholders — replace `<...>` with your LAN values)

| Item | Placeholder | Example shape | Notes |
|------|-------------|---------------|-------|
| Worker VMID range | `<pool-start>`–`<pool-end>` | a contiguous block | Convention, made real by the bounded scan + DB unique reservation + the `/pool` ACL fence |
| Subnet | `<subnet>` | a `/<prefix>` LAN | the bridge's subnet |
| Prefix | `<prefix>` | CIDR prefix length | e.g. a `/24` |
| Gateway | `<gw>` | bare gateway IP | `gw=` takes a bare IP |
| Bridge | `<bridge>` | the LAN bridge | must already exist on the host |

### VMID → IP formula

Map each worker `VMID` to a host octet within the subnet, e.g. with a `/24` LAN
and a worker range inside one octet:

```
worker VMID  ->  <subnet>.<last-octet>/<prefix>   gateway <gw>   bridge <bridge>
```

Pick a deterministic, collision-free mapping from VMID to the host octet (e.g.
derive the last octet directly from the VMID's low digits). The control plane
computes the same address from the VMID, so the mapping is the single source of
truth for both `pct set net0` and the control plane's IP computation.

### Applied at clone time (runtime, not priming)

The per-clone network set runs inside the create saga (needs `VM.Config.Network`,
which `00-api-user-role.sh` grants):

```bash
pct set <vmid> -net0 name=eth0,bridge=<bridge>,ip=<subnet>.<oct>/<prefix>,gw=<gw>
```

`ip=` takes CIDR; `gw=` is a bare gateway IP.

## The load-bearing obligation: exclude the worker range from DHCP

**Reserve the worker IP range OUT of your DHCP server's pool** (router / pfSense
/ dnsmasq — this is an **off-host** change, no Proxmox command). If DHCP can
hand out an address inside `<subnet>.<pool-start-octet>`–`<subnet>.<pool-end-octet>`,
a worker boot causes a LAN conflict. This off-host DHCP exclusion is the
load-bearing collision-avoidance step — it has no Proxmox-side enforcement, so it
is on the operator to configure and verify.

## Keep infra OUTSIDE the worker range

- The **golden template** VMID and IP live OUTSIDE the worker range.
- The **control plane** lives OUTSIDE the worker range.

This guarantees the worker range is exclusively ephemeral clones, so destroying a
worker can never collide with persistent infrastructure.

## Operator checklist

- [ ] Bridge `<bridge>` exists and is the LAN bridge (`ip link show <bridge>`).
- [ ] Worker VMID range `<pool-start>`–`<pool-end>` chosen and recorded.
- [ ] VMID → IP mapping defined and matches the control plane's computation.
- [ ] Worker IP range **excluded from DHCP** (off-host) and verified.
- [ ] Template + control-plane addresses are OUTSIDE the worker range.
