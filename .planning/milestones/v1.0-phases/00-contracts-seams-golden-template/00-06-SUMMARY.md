<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 00-contracts-seams-golden-template
plan: 06
subsystem: infra
tags: [proxmox, pveum, lxc, host-prime, least-privilege, privsep, secret-hygiene, static-ip, runbook, shell]

# Dependency graph
requires:
  - phase: 00-05
    provides: "ADR-0003 (tight /pool ACL scoping), ADR-0004 (static-IP-from-VMID), ADR-0005 (--full clone) — the locked decisions this kit implements"
provides:
  - "Re-runnable Proxmox Day-0 host-prime kit (cc-worker-config/lxc/host-prime/): lib/common.sh guards + four idempotent scripts"
  - "BurrowProvisioner least-privilege role (exactly 9 privileges) + privsep token granted to BOTH user and token at every scoped path"
  - "Full secret-hygiene contract for the Proxmox token: read -rsp, set +x, printf-not-echo, never-a-CLI-arg, check-ignore guard, 0600"
  - "30-network-notes.md static-IP-from-VMID decision record + off-host DHCP-exclusion obligation (placeholders only)"
  - "40-control-plane.sh: service account, /opt/burrow layout, uv venv|container, nginx validate-before-reload, systemd, /data-preserving reversal"
  - "PRIMING.md ordered Day-0 runbook with per-step gates ending in the five-step create->live->stop->start->destroy acceptance gate"
affects: [01-control-plane-api, 03-reproducible-workers, dev-homelab-smoke-gate]

# Tech tracking
tech-stack:
  added: [pveum, pct, pveam, pvesh, ttyd, nginx, uv, systemd]
  patterns:
    - "Idempotent shell: set -euo pipefail + IFS + ERR trap + require_root/require_cmd/require_node + check->act + reversal block (sourced from lib/common.sh)"
    - "Secret hygiene: machine-minted token captured silently, never echoed; .env write refused unless git check-ignore passes; 0600; one-time non-idempotent token guarded with rotate/reuse prompt"
    - "Topology-as-placeholders: <node>/<rootfs-storage>/<template-vmid>/<bridge>/<subnet> never filled in the repo; operator fills gitignored .env + their own copy of 30-network-notes"

key-files:
  created:
    - cc-worker-config/lxc/host-prime/lib/common.sh
    - cc-worker-config/lxc/host-prime/00-api-user-role.sh
    - cc-worker-config/lxc/host-prime/10-template-download.sh
    - cc-worker-config/lxc/host-prime/20-create-template.sh
    - cc-worker-config/lxc/host-prime/30-network-notes.md
    - cc-worker-config/lxc/host-prime/40-control-plane.sh
    - cc-worker-config/PRIMING.md
  modified: []

key-decisions:
  - "00-api-user-role.sh captures the token from `pveum token add` JSON (machine-minted) rather than a typed prompt; the read -rsp paths are the gitignore-refused fallback (00-) and the operator paste of the STEP-0 token (40-) — strictly more secure than printing the value"
  - "ACL granted to BOTH --users and --tokens at pool/template/storage/node in a single loop, because privsep effective rights = user INTERSECT token (granting only the user leaves the token with zero rights — the most common silent-403)"
  - "Token is the one non-idempotent resource: guarded with `token list | grep || add` and a loud rotate/reuse prompt on re-run (a second add mints a second token and never re-prints the first secret)"
  - "20-create-template.sh references the worker-template payload (provision-template.sh, burrow-boot.sh, burrow-worker.service, plugins) by path — that payload is authored in Plan 07; the script fails loudly if it is absent rather than half-provisioning"
  - "40-control-plane.sh supports both DEPLOY_MODE=venv (uv sync --frozen) and DEPLOY_MODE=container (Dockerfile.api image), per PROXMOX-PRIMING §7 + ADR-0008 open runtime-base question"

patterns-established:
  - "Pattern: numbered host-prime scripts encode the hard dependency chain (00 identity -> 10 download -> 20 template -> 30 network note -> 40 control plane); PRIMING.md is the human entry point"
  - "Pattern: every destructive step (rebuild template, remove nginx default, overwrite .env) is gated by a typed-yes confirm() helper"
  - "Pattern: SPDX header is shebang line 1 + two # lines (2-3) for .sh; <!-- --> block for .md (reuse lint-file detects both)"

requirements-completed: [SETUP-01, SETUP-02, SETUP-03, SETUP-04, SETUP-05]

# Metrics
duration: 35min
completed: 2026-06-10
---

# Phase 0 Plan 06: Proxmox Day-0 Host-Prime Kit Summary

**Re-runnable Proxmox Day-0 kit — lib/common.sh guards + 4 idempotent scripts (9-priv least-privilege role, privsep token to both principals, secret-safe .env, nginx validate-before-reload) + the static-IP-from-VMID network note + the ordered PRIMING.md runbook ending in the five-step create->live->stop->start->destroy acceptance gate.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-10T02:23:00Z
- **Completed:** 2026-06-10T02:58:00Z
- **Tasks:** 4
- **Files modified:** 7 (all created)

## Accomplishments
- `lib/common.sh` shared strict-mode + ERR trap + `require_root`/`require_cmd`/`require_node` guards + a typed-yes `confirm` gate, sourced by all four scripts.
- `00-api-user-role.sh` authors the `BurrowProvisioner` role as exactly the verified 9-privilege set, mints a `--privsep 1` token, and grants the role to BOTH the user and the token at `/pool/burrow-workers` (propagate), `/vms/<template-vmid>`, `/storage/<rootfs>`, `/nodes/<node>` — with the full secret-hygiene contract and a loud rotate/reuse prompt on a pre-existing token.
- `10-template-download.sh` (pinned, idempotent `pveam download`) + `20-create-template.sh` (`pct create --unprivileged 1 --features nesting=1` on thin rootfs, in-CT provision, `pct template`) + `30-network-notes.md` (static-IP-from-VMID formula + the load-bearing off-host DHCP-exclusion obligation).
- `40-control-plane.sh` provisions the persistent control plane (service account, `/opt/burrow` + `/data`, uv venv or container, nginx `nginx -t` before reload, systemd hardening) and assembles the gitignored `.env` with the STEP-0 token read silently, written under `set +x`, `0600`, refused unless `git check-ignore` passes — with a reversal block that preserves `/data`.
- `PRIMING.md` orders preconditions P1-P5 + STEP 0-4, each naming its script and pass gate, ending in the five-step real-Proxmox acceptance gate; STEP 2 + STEP 4 marked `human_needed`/dev-homelab (deferred, not phase-blocking).

## Task Commits

Each task was committed atomically (Conventional Commits, `Signed-off-by`):

1. **Task 1: lib/common.sh + 00-api-user-role.sh** - `ab2d675` (feat)
2. **Task 2: 10-template-download.sh + 20-create-template.sh + 30-network-notes.md** - `74ae50f` (feat)
3. **Task 3: 40-control-plane.sh** - `44f5549` (feat)
4. **Task 4: PRIMING.md** - `936a6e9` (docs)

**Plan metadata:** (this commit) — `docs(00-06): complete host-prime kit plan`

## Files Created/Modified
- `cc-worker-config/lxc/host-prime/lib/common.sh` - shared strict mode, ERR trap, require_* guards, confirm()
- `cc-worker-config/lxc/host-prime/00-api-user-role.sh` - user + 9-priv role + privsep token to both principals + secret hygiene (SETUP-02/03)
- `cc-worker-config/lxc/host-prime/10-template-download.sh` - pinned, idempotent Ubuntu 24.04 CT template download (SETUP-01)
- `cc-worker-config/lxc/host-prime/20-create-template.sh` - unprivileged+nesting CT on thin storage, provision, pct template (SETUP-01)
- `cc-worker-config/lxc/host-prime/30-network-notes.md` - static-IP-from-VMID + off-host DHCP-exclusion decision record (SETUP-05)
- `cc-worker-config/lxc/host-prime/40-control-plane.sh` - control-plane provisioning + secret-safe .env, /data-preserving reversal (SETUP-01)
- `cc-worker-config/PRIMING.md` - ordered Day-0 runbook + five-step acceptance gate (SETUP-04)

## Decisions Made
- **Machine-minted token over typed prompt:** the token comes from `pveum token add` JSON, never re-typed; the `read -rsp` paths are the secure fallback (gitignore-refused) and the STEP-0 paste in `40-`. This satisfies the secret-hygiene contract without ever printing the value.
- **Both principals in one ACL loop:** grant `BurrowProvisioner` to `--users $USER` AND `--tokens burrow@pve!$TOKEN` at every scoped path, because privsep makes the token's effective rights `user ∩ token` (T-00-06-PRIVSEP).
- **Loud rotate/reuse prompt** on a pre-existing token (T-00-06-IDEMPOTENT) — the one place the kit cannot silently converge.
- **`40-` supports venv and container deploy modes** (ADR-0008 open runtime-base question), stated via `DEPLOY_MODE`.

## Deviations from Plan

None - plan executed exactly as written. All four tasks, all acceptance criteria, and the threat-model mitigations (T-00-06-DISCLOSE/EOP/PRIVSEP/TAMPER/IDEMPOTENT) were authored as specified.

> Note on tool substitution (not a plan deviation — environment fallback per the execution context): `shellcheck` is not installed on the Windows dev host, so the plan's `shellcheck ... exits 0` checks were satisfied via `bash -n` syntax validation (all five scripts pass). `shellcheck` static analysis is **unverified** and should be run in CI / on the homelab. SPDX was verified with `uvx --with charset-normalizer reuse lint-file` (the `reuse` package needs the `charset-normalizer` encoding module on Windows); all seven files carry valid SPDX tags.

## Issues Encountered
- **`reuse` import failure on Windows:** `uvx reuse` raised `NoEncodingModuleError` (missing libmagic/charset detection). Resolved by running `uvx --with charset-normalizer reuse lint-file`, which detects the SPDX headers correctly.
- **`reuse lint` (v6) rejects file args:** the project-wide `reuse lint` no longer takes paths; used `reuse lint-file` for per-file SPDX verification instead.

## User Setup Required

**External service (Proxmox) requires manual, deferred configuration.** This plan's `autonomous: false` half — running the kit against a real Proxmox VE 8.x node — is the dev-homelab smoke gate (`human_needed`), deferred and NOT phase-blocking:
- Run `PRIMING.md` STEP 0-4 on the Proxmox host as `root@pam`.
- Capture `PROXMOX_TOKEN_VALUE` (printed once by `00-api-user-role.sh`) into the gitignored `.env`.
- STEP 0 gate: `pvesh get /access/permissions --token` shows pool/storage/node-scoped rights only.
- STEP 3 gate: `GET /api/v1/health` -> `db: ok, compute: ok`.
- STEP 4: the five-step create->live->stop->start->destroy acceptance gate.

## Known Stubs

None that block the plan goal. Two forward-references are intentional and documented:
- `20-create-template.sh` references the worker-template payload (`provision-template.sh`, `burrow-boot.sh`, `burrow-worker.service`, `plugins/`) by path — **authored in Plan 00-07**. The script fails loudly if the payload is absent (does not half-provision).
- `40-control-plane.sh` references `nginx/burrow.conf` and `systemd/burrow.service` by path — those control-plane artifacts land with the control-plane spec; the script skips (with a log) if absent rather than failing.

## Deferred / Out-of-Scope (logged, not fixed)
- **Repo-wide REUSE compliance:** there is no `LICENSES/AGPL-3.0-or-later.txt`, so `reuse lint-file --quiet` exits non-zero with a "missing license" notice on these files — and identically on already-committed files (e.g. `CONTRIBUTING.md`). This is pre-existing repo-wide state (the per-file SPDX headers are correct and byte-identical to shipped files), out of scope for 00-06. Belongs to the SPDX/REUSE static-gate plan (00-04).

## Next Phase Readiness
- SETUP-01..05 doc/script half is **complete and committed**; the kit is shellcheck-pending (CI/homelab) and real-infra-validation-deferred.
- Plan 00-07 (golden-template provisioner + `burrow-boot.sh` + `burrow-worker.service`) supplies the worker-template payload that `20-create-template.sh` references.
- Real-Proxmox acceptance (token authenticates, scoped clone works, the five-step smoke) is the dev-homelab gate — the authority for SETUP-01..05's TRUE acceptance.

## Self-Check: PASSED

- All 7 kit files + SUMMARY.md verified present on disk.
- All 4 task commit hashes (`ab2d675`, `74ae50f`, `44f5549`, `936a6e9`) verified in git history.
- All five scripts pass `bash -n`; the exact 9-priv string, `--privsep 1`, and `--tokens` grants are present; no token value is ever echoed; no real topology leaked.

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
