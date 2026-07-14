<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 22: Live Homelab Acceptance Capstone - Context

**Gathered:** 2026-07-14
**Status:** Ready for the operator (human UAT capstone)
**Mode:** Operator-run human UAT on real Proxmox. RUNBOOK, NOT CODE. No product
code ships in this phase; the deliverable is a passed acceptance checklist.

<domain>
## Phase Boundary

Phase 22 is the human-UAT capstone that closes v1.4. It proves the milestone on the
real Proxmox homelab: the remaining ACC-01 lifecycle items (6 to 11, carried from
v1.3) pass on real CTs across two live worker nodes, and the GUI credential store is
verified live on den01. Everything here is run by a human against real infrastructure.

Scope of this phase (the five success criteria):

- **ACC-04 (reaper / idle / capacity):** the reaper destroys a real injected orphan
  LXC and frees its VMID on a non-default node; idle auto-stop fires after the real
  `idle_window_s` and a brief reconnect does not trip it; capacity holds under real
  concurrent creates.
- **ACC-04 (item 9, 2nd node):** real least-loaded node selection lands correctly
  across two live worker nodes.
- **ACC-04 (persistence):** a persistent workspace survives a real stop then start
  with disk and scrollback intact, and the reaper never destroys a persistent stopped
  workspace.
- **ACC-05 (credential GUI on den01):** migration `004` applies on the real SQLite, a
  GUI-set Proxmox token applies without a control-plane restart and survives one.
- **ACC-06 rider (live re-verify):** a homelab-pulled `@sha256:` image re-verifies
  with `cosign verify` and `gh attestation verify`. ACC-06 was already proven green on
  the GitHub runner in Phase 20; this is the live re-verify against a pulled image.

This is NOT CI-provable by design: CI is hermetic and never touches real Proxmox.
Every item lands `result: [pending]` until the operator runs it on the homelab.
</domain>

<dependencies>
## Dependencies

- **Phase 16** (credential backend landed on green `main`).
- **Phase 18** (credential GUI: SetupWizard admin-secret and credentials steps, the
  admin-gated Credentials screen, the `X-Burrow-Admin` header, `BURROW_SECRET_KEY`
  onboarding auto-generation).
- **Phase 19** (async-202 create: `POST /api/v1/workspaces` returns `202` + a
  `creating` row, boot saga runs in a tracked background task, so a slow real boot
  never `504`s).
- **Phase 20** (the signed v1.4 release to deploy and re-verify: cosign keyless +
  SLSA attestation on the published `@sha256:` digest).

ACC-01 items 1 to 5 (the H9 core: create, live terminal, stop, start, destroy)
already PASSED 2026-07-12 on den01 via the control-plane API plus den01 verification.
This phase exercises the remaining items 6 to 11 plus the ACC-05 and ACC-06 riders.
</dependencies>

<topology>
## Live Topology Summary

- **den01** = Proxmox node. API `10.0.0.6` (cert SAN carries the IP; TLS validated
  against the node CA, never disabled). Key-based SSH as `root@10.0.0.6`. Golden
  template VMID **9000**. Token `burrow@pve!burrow`, role `BurrowProvisioner`. Worker
  clones are added to `/pool/burrow-workers` (ADR-0003). den01 is the `default_node`.
- **lintool03** = Ubuntu Docker box, LAN `10.0.1.38`, hosts the control plane.
  Checkout at `~/burrow` as `bravebear@lintool03`; stack is `compose.prod.yml`;
  host port **:8081** (a local remap of the committed `80:8080`) fronts burrow-web
  nginx, which proxies `/api` + `/ws` to burrow-api. `/opt/burrow/.env` holds the
  Proxmox token, `BURROW_SECRET_KEY`, `ALLOWED_ORIGIN`, and
  `DATABASE_PATH=/data/burrow.db`. The node CA is at `/etc/burrow/pve-ca.pem`.
- **NPM** fronts the control plane at `https://burrow.local.bravebearstudios.com`
  (TLS + WebSocket on).
- **Health is `:8081` OR the NPM domain, NEVER `:80`** (`:80` on lintool03 is ntfy
  and returns `{"code":40401,...}`). A healthy control plane reports
  `status: ok, db: ok, compute: ok`.
- Worker VMIDs **969 to 1022** map to IPs `10.0.0.201` to `10.0.0.254` (above the
  DHCP pool `.100` to `.200`, no exclusion needed).
- The golden template bakes `CONTROL_PLANE=http://10.0.1.38:8081` into
  `/etc/burrow/worker.env`, so a booted worker calls back to the control plane.

### Load-bearing constraint

`BURROW_SECRET_KEY` in `/opt/burrow/.env` MUST stay unchanged across the redeploy. It
is the Fernet master key for the credential store; if it changes, the stored,
encrypted Proxmox token and GitHub PAT can no longer be decrypted, and ACC-05's
"survives a restart" check fails (the resolver falls back to the `.env` token and the
stored last4 is lost).
</topology>

<operator_notes>
## Operator Notes

- **The operator runs every DESTROY step.** The control plane's auto-mode safety
  classifier blocks the agent from destroying a workspace it did not create, so all
  `DELETE /workspaces/{id}` calls and all den01 `pct destroy` commands are
  operator-run. The runbook marks these explicitly.
- **Novice framing.** The UAT doc gives exact copy-paste commands, the expected output
  for each, and a recovery hint where a step can fail. Substitute the placeholders
  (the 2nd node name, the live `idle_window_s`, the exact release tag / digest) with
  the confirmed live values before running.
</operator_notes>
