<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# PRIMING.md — Burrow Day-0 Operator Runbook (SETUP-04)

Fresh operator, bare Proxmox cluster, to first workspace. Run the numbered
host-prime scripts in order; each step has a **pass gate** that localizes
failure before the next step. All topology is a placeholder — fill your LAN
values into the gitignored `.env` and `lxc/host-prime/30-network-notes.md`.

> Source: `.planning/research/PROXMOX-PRIMING.md` §8. Scripts live in
> `lxc/host-prime/`. The token is the single high-value secret: it prints once,
> goes into a gitignored `.env`, and is never committed/echoed/logged.

> **Deferred (dev-homelab / `human_needed`).** STEP 2's manual clone gate and
> STEP 4's five-step acceptance gate require a real Proxmox node. They are the
> deferred dev-homelab smoke gate — authored here, validated on real infra. They
> do NOT block CI or this phase.

## Preconditions (operator confirms; runbook checks)

| ID | Precondition |
|----|--------------|
| P1 | PVE 8.x cluster reachable; you have `root@pam` on a node. |
| P2 | A CT-rootfs storage exists (thin: lvmthin/zfspool) **and** a vztmpl (dir) storage. |
| P3 | The LAN bridge `<bridge>` exists on the LAN the control plane shares. |
| P4 | DNS / host entry for the control-plane box. |
| P5 | `cc-worker-config` cloned on the node; `.env` is gitignored in the burrow checkout. |

## STEP 0 — Identity & least privilege  · `lxc/host-prime/00-api-user-role.sh`

Run as `root@pam`. Creates `burrow@pve` (token-only), the `BurrowProvisioner`
role (the verified 9-privilege set), the `burrow-workers` pool, and a `privsep=1`
API token, then grants the role to **BOTH the user and the token** at the
pool/template/storage/node paths.

> **Copy the token value at the moment it is captured — it is shown/written once
> and is unrecoverable.** It lands in your gitignored `.env` as
> `PROXMOX_TOKEN_VALUE` and is never echoed to the terminal.

**GATE:** the token resolves to pool/storage/node-scoped rights only — and
**nothing** on out-of-pool VMIDs:

```bash
pvesh get /access/permissions --token "burrow@pve!burrow=<uuid>"
```

This `--token` check is authoritative: it shows the **token's** effective
rights after the user∩token privsep intersection, catching the most common
mistake (granted the user but not the token).

## STEP 1 — Network decision  · `lxc/host-prime/30-network-notes.md`

Record the static-IP-from-VMID scheme for YOUR LAN: `VMID -> <subnet>.<oct>`,
gateway `<gw>`, bridge `<bridge>`, worker range `<pool-start>`–`<pool-end>`.
**Reserve that IP range OUT of DHCP (off-host).** This is the single source of
truth for `pct set net0` AND the control plane's IP computation.

**GATE:** the worker range is excluded from DHCP and verified; the template and
control plane sit OUTSIDE the worker range. (See ADR-0004.)

## STEP 2 — Golden template  · `lxc/host-prime/10-template-download.sh` then `20-create-template.sh`

- `10-template-download.sh`: `pveam download` the Ubuntu 24.04 CT template.
- `20-create-template.sh`: `pct create <template-vmid>` (`--unprivileged 1`,
  `--features nesting=1`) on thin rootfs, provision inside, then `pct template`.

**GATE (manual, dev-homelab / `human_needed` — deferred, not phase-blocking):**
clone the template once by hand with `--full`, start it, confirm `ttyd` comes up
on the LAN interface and `claude` launches, then destroy the test clone.

## STEP 3 — Control plane  · `lxc/host-prime/40-control-plane.sh`

Creates the `burrow` user, `/opt/burrow` + `/data`, the uv venv (or container
image), the nginx site (validated with `nginx -t` before reload), and
`burrow.service`. Assembles `.env`: paste the STEP-0 token at the **hidden**
prompt (never echoed; `.env` ends `0600`).

**GATE:** the health endpoint reports both subsystems healthy:

```bash
curl http://127.0.0.1:8000/api/v1/health   # expect  db: ok,  compute: ok
```

`compute: ok` proves the token + scoped ACL actually authenticate end-to-end.

## STEP 4 — First workspace: the five-step acceptance gate  · LAN browser smoke

**GATE (dev-homelab / `human_needed` — deferred, not phase-blocking).** The real
acceptance test, run from a LAN browser against the live control plane:

| # | Action | Expected |
|---|--------|----------|
| 1 | **create** | pick a small repo + branch, submit; a worker CT is cloned `--full` |
| 2 | **live** | the terminal panel shows an interactive, resizable `claude` session |
| 3 | **stop** | status `stopped`, the LXC is stopped, disk preserved |
| 4 | **start** | status `running`, the terminal reconnects to the SAME session |
| 5 | **destroy** | the LXC is gone, the VMID is freed, the row is soft-deleted |

**ACCEPTANCE:** all five succeed end-to-end against real Proxmox. This is the
Definition-of-Done for "Burrow can create its first workspace" and validates
UPID waits, static-IP reachability, the ttyd subprotocol bridge, and saga
compensation in one operator-visible pass.

Each earlier gate **localizes failure** so that when the five-step smoke test
fails, it fails for a workspace-logic reason — not an over/under-scoped token or
a ttyd bound to `lo`.

## Operator verification commands (from the control-plane host, with the token)

```bash
export PVE_TOKEN='burrow@pve!burrow=<uuid>'           # from .env
api(){ curl -sk -H "Authorization: PVEAPIToken=$PVE_TOKEN" "https://<pve-host>:8006/api2/json$1"; }
api /cluster/nextid                                   # token auth (401 = bad token)
api /nodes/<node>/status                              # 403 = missing Sys.Audit at /nodes/<node>
api /nodes/<node>/lxc/<template-vmid>/config          # can see the template (VM.Clone/Audit)
api /nodes/<node>/lxc/<out-of-pool-vmid>/config       # NEGATIVE: expect 403 if scoped to /pool
pvesh get /access/permissions --token "$PVE_TOKEN"    # authoritative scope check (catches privsep mistake)
```
