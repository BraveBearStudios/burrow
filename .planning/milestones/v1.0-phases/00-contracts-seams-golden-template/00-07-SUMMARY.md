<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 00-contracts-seams-golden-template
plan: 07
subsystem: infra
tags: [golden-template, worker, lxc, ttyd, systemd, boot, pull-at-boot, claude-code, node22, shell, SC-8, SC-9]

# Dependency graph
requires:
  - phase: 00-05
    provides: "ADR-0002 (pull-at-boot), ADR-0006 (ttyd persistent / drop --once), ADR-0007 (ttyd LAN bind / WORK-04) — the frozen decisions this plan implements in shell"
  - phase: 00-06
    provides: "20-create-template.sh, which pushes this plan's worker-template payload into the CT and references the systemd unit by path"
provides:
  - "provision-template.sh: reproducible golden-template provisioner (WORK-01) — Ubuntu 24.04 + Node 22 (setup_22.x) + pinned @anthropic-ai/claude-code@2.1.170 + ttyd + baked binary/npm-global plugins; enables the boot unit"
  - "burrow-boot.sh: SC-corrected boot script (WORK-04) — PERSISTENT ttyd (no --once, SC-8) bound to the worker LAN interface (--interface 0.0.0.0, SC-9) on :7681; pull-at-boot config fetch is a documented Phase-3 stub keeping secrets off the worker env"
  - "burrow-worker.service: minimal systemd unit (ExecStart=/opt/burrow-boot.sh, Type=simple, Restart=on-failure) — secret-free, no topology"
affects: [01-control-plane-api, 03-reproducible-workers, dev-homelab-smoke-gate]

# Tech tracking
tech-stack:
  added: [ttyd, nodejs-22, "@anthropic-ai/claude-code@2.1.170", systemd, git, build-essential]
  patterns:
    - "SC-corrected ttyd invocation (FROZEN): exec ttyd --port 7681 --writable --interface 0.0.0.0 bash -lc '...' — NO --once (persistent, detach!=terminate), LAN bind (not lo)"
    - "Pull-at-boot stub: worker knows its VMID (SC-6), will GET <CONTROL_PLANE>/api/v1/internal/bootconfig/<vmid> for non-secret config + a short-lived git credential it DISCARDS — never written to /etc/burrow/worker.env (SC-4 / Pitfall 13)"
    - "Reproducible template: pinned NodeSource setup_22.x ref + exact claude-code pin; baked plugins are binary + npm-global types ONLY (claude-plugin types pull at boot, Phase 3)"

key-files:
  created:
    - cc-worker-config/lxc/worker-template/provision-template.sh
    - cc-worker-config/lxc/worker-template/burrow-boot.sh
    - cc-worker-config/systemd/burrow-worker.service
  modified:
    - cc-worker-config/lxc/host-prime/20-create-template.sh

key-decisions:
  - "systemd unit canonicalized under cc-worker-config/systemd/ (per Plan 00-07, the most recent doc) — NOT cc-worker-config/lxc/worker-template/ where Plan 00-06's 20-create-template.sh originally expected it. Resolved the conflict by repointing 20-create-template.sh's WORKER_UNIT at the canonical systemd/ path."
  - "Did NOT copy the tech-spec §9.3 boot snippet: its --once (SC-8) and --interface lo (SC-9) are both reversed; the spec §9.2 provisioner's cloud-init comment is removed (pull-at-boot fetches the env, ADR-0002)."
  - "burrow-boot.sh requires CONTROL_PLANE (${CONTROL_PLANE:?...}) and defaults CONFIG_*/PROJECT_* to env with a main branch default; the live fetch + auth is a TODO(Phase 3) stub — the shape is right, the secret handling is deferred but documented."
  - "provision-template.sh guards the rtk plugin install (skips with a log if /tmp/plugins/rtk/install.sh is absent) since 20-create-template.sh pushes plugins conditionally."

patterns-established:
  - "Worker-template payload (provision-template.sh, burrow-boot.sh, plugins/) lives under cc-worker-config/lxc/worker-template/; the systemd unit lives under cc-worker-config/systemd/; host-prime/20-create-template.sh pushes them into the CT before pct template."
  - "SPDX: shebang line 1 + two # lines (2-3) for .sh; two # lines (1-2) for the systemd .service file."

requirements-completed: [WORK-01, WORK-04]

# Metrics
duration: 20min
completed: 2026-06-10
---

# Phase 0 Plan 07: Golden-Template Provisioner + SC-Corrected Boot Script + systemd Unit

**The frozen worker-template shell artifacts — a reproducible `provision-template.sh` (Ubuntu 24.04 + Node 22 + pinned `@anthropic-ai/claude-code@2.1.170` + ttyd + baked plugins, boot unit enabled), an SC-corrected `burrow-boot.sh` (PERSISTENT, LAN-bound ttyd on :7681 + a documented pull-at-boot stub that keeps secrets off the worker env), and the minimal `burrow-worker.service` unit. The tech-spec's broken `--once` / `--interface lo` boot snippet was NOT copied; the SC-corrected RESEARCH skeletons were.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files modified:** 4 (3 created, 1 edited)

## Accomplishments
- `provision-template.sh` (WORK-01) bakes the worker software baseline reproducibly: `apt` base + `ttyd`, Node 22 via NodeSource `setup_22.x`, the exact `@anthropic-ai/claude-code@2.1.170` pin, the binary + npm-global baked plugins (rtk via `install.sh`, gsd via `npm i -g`), installs `/opt/burrow-boot.sh` + the systemd unit, and `systemctl enable`s the boot unit. The `/etc/burrow/worker.env` placeholder is created with NO cloud-init comment (pull-at-boot fetches it).
- `burrow-boot.sh` (WORK-04) launches the FROZEN ttyd invocation — `exec ttyd --port 7681 --writable --interface 0.0.0.0 bash -lc "..."` — with NO `--once` (SC-8: persistent; tab close detaches, never terminates) and LAN bind (SC-9: `0.0.0.0`, not `lo`). The pull-at-boot config fetch is a documented `TODO(Phase 3)` stub: the worker will GET non-secret config from `<CONTROL_PLANE>/api/v1/internal/bootconfig/<vmid>` and use+discard a short-lived git credential — never written to `/etc/burrow/worker.env`.
- `burrow-worker.service` is a minimal, secret-free unit: `ExecStart=/opt/burrow-boot.sh`, `Type=simple`, `Restart=on-failure`, `After`/`Wants=network-online.target`, `WantedBy=multi-user.target`.
- Resolved the unit-location conflict between Plan 00-06 and Plan 00-07 by canonicalizing under `cc-worker-config/systemd/` and repointing `20-create-template.sh`'s `WORKER_UNIT`.

## Task Commits

Each task was committed atomically (Conventional Commits, `Signed-off-by`):

1. **Task 1: provision-template.sh** — `aa334c0` (feat)
2. **Task 2: burrow-boot.sh** — `6d0dcbf` (feat)
3. **Task 3: burrow-worker.service + host-prime path fix** — `001a8f6` (feat)

## Files Created/Modified
- `cc-worker-config/lxc/worker-template/provision-template.sh` — reproducible golden-template provisioner (WORK-01)
- `cc-worker-config/lxc/worker-template/burrow-boot.sh` — persistent, LAN-bound ttyd + pull-at-boot stub (WORK-04)
- `cc-worker-config/systemd/burrow-worker.service` — minimal systemd unit, `ExecStart=/opt/burrow-boot.sh`
- `cc-worker-config/lxc/host-prime/20-create-template.sh` — repointed `WORKER_UNIT` at the canonical `systemd/` path (+ comment)

## Decisions Made
- **SC corrections applied, spec snippet rejected:** the tech-spec §9.3 boot snippet's `--once` and `--interface lo` are both SC-reversed; authored from the SC-corrected RESEARCH skeleton instead. The §9.2 provisioner's "overwritten by cloud-init" comment was removed (pull-at-boot, ADR-0002).
- **Unit lives under `cc-worker-config/systemd/`** (Plan 00-07, most recent doc wins) and `20-create-template.sh` was updated to find it there.
- **Secrets off the worker env:** `burrow-boot.sh` documents (in three comment blocks) that no secret is written to `/etc/burrow/worker.env`; the credential is fetched, used, and discarded (T-00-07-SECRET mitigated).

## Deviations from Plan
- **One small edit beyond the three task files:** the plan named `cc-worker-config/systemd/burrow-worker.service` as the unit's home, but the already-committed `20-create-template.sh` (Plan 00-06) expected it under `worker-template/`. Per "most recent doc wins, note the conflict," the unit was authored at the plan's location and `20-create-template.sh`'s `WORKER_UNIT` reference (+ a header comment) was updated so the host-prime kit still locates it. Committed together in Task 3.

> Note on tool substitution (environment fallback, not a plan deviation): `shellcheck` is not installed on the Windows dev host, so the plan's `shellcheck ... exits 0` checks were satisfied via `bash -n` (all three scripts pass). `shellcheck` static analysis remains **unverified** — run it in CI / on the homelab. SPDX was verified with `uvx --with charset-normalizer reuse lint-file` (Windows needs the `charset-normalizer` encoding module); all three files carry valid SPDX tags.

## Issues Encountered
- **`reuse lint-file` "missing license" notice:** identical pre-existing repo-wide state documented in 00-06 — there is no `LICENSES/AGPL-3.0-or-later.txt`, so `reuse` reports "missing license" on every file (including already-committed ones). The per-file SPDX *tags* are correct and detected; adding the license text file belongs to the SPDX/REUSE static-gate plan (00-04). Exit code is 0.

## User Setup Required

**External service (Proxmox) requires manual, deferred validation.** This plan's `autonomous: false` half — building a real template and clone-booting it — is the dev-homelab smoke gate (`human_needed`), deferred and NOT phase-blocking:
- Build the golden template: run `PRIMING.md` STEP 2 (`20-create-template.sh` pushes this payload into the CT, runs `provision-template.sh`, then `pct template`).
- Clone-boot once (`--full`) and verify: ttyd is reachable on the worker LAN address at `:7681`, `claude` launches, and closing the browser tab does NOT terminate the session (persistent, SC-8).

## Known Stubs
- **Pull-at-boot fetch (`burrow-boot.sh`)** is a documented `TODO(Phase 3)` stub. Phase 0 freezes the ttyd invocation and the secret-handling contract (fetch+use+discard, never persisted); the live `GET /api/v1/internal/bootconfig/<vmid>` + short-lived-credential auth lands Phase 3 (the endpoint contract is Phase 1). The script reads `CONFIG_*`/`PROJECT_*` from env in the interim.

## Deferred / Out-of-Scope (logged, not fixed)
- **Real-infra acceptance of WORK-01 / WORK-04** (template builds, clone boots, ttyd reachable on LAN, `claude` launches, persistent ttyd survives a tab close) — dev-homelab smoke gate, `human_needed`, NOT phase-blocking.
- **`shellcheck` static analysis** — unavailable on the Windows host; run in CI/homelab.
- **Repo-wide REUSE compliance** (`LICENSES/AGPL-3.0-or-later.txt`) — belongs to plan 00-04.

## Next Phase Readiness
- WORK-01 + WORK-04 script half is **complete and committed**; the worker-template payload that `20-create-template.sh` (00-06) references now exists.
- Phase 1 owns the bootconfig endpoint contract (`GET /api/v1/internal/bootconfig/<vmid>`); Phase 3 fills the live pull-at-boot fetch + auth in `burrow-boot.sh`.
- Real-template build/boot + LAN ttyd reachability is the dev-homelab gate — the authority for WORK-01/WORK-04's TRUE acceptance.

## Self-Check: PASSED

- All 3 created files + the edited `20-create-template.sh` + SUMMARY.md verified present on disk.
- All 3 task commit hashes (`aa334c0`, `6d0dcbf`, `001a8f6`) verified in git history.
- All three scripts pass `bash -n`; `burrow-boot.sh` has NO `--once` and NO `--interface lo`, and DOES have `--interface 0.0.0.0` + `--port 7681`; `provision-template.sh` pins claude-code@2.1.170, installs ttyd, enables the unit, and carries no cloud-init comment; the unit has `ExecStart=/opt/burrow-boot.sh` + all three sections and no secrets/topology.

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
