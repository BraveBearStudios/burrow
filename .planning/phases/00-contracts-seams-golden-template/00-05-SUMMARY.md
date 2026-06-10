<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 00-contracts-seams-golden-template
plan: 05
subsystem: docs
tags: [adr, nygard, pull-at-boot, acl-scoping, static-ip, clone-full, ttyd, stack-bumps, spdx]

# Dependency graph
requires: []
provides:
  - "Eight Nygard-style ADRs in docs/adr/ recording every Phase-0 deviation from the spec happy-path"
  - "ADR-0002: pull-at-boot locked as the boot-config mechanism (the contract Phase 1 injectBootConfig + bootconfig endpoint build on)"
  - "ADR-0007: ttyd LAN-bind decision (WORK-04 documentation half) with its security dimension"
  - "ADR-0008: consolidated stack-version-bump record (Vite 8, TS 6, Biome 2, Vitest 4, @xterm 6, mypy 2, react-mosaic 6.2.0, Tailwind v4)"
affects: [00-06-host-prime-kit, 00-07-golden-template, phase-1-control-plane-api, phase-3-reproducible-workers]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nygard ADR format (Status/Context/Decision/Consequences/Revisit trigger) for every baseline deviation, per CONTRIBUTING.md"
    - "Consolidated ADR for deviations sharing one rationale + one evidence base (ADR-0008 over eight near-identical files)"

key-files:
  created:
    - docs/adr/ADR-0001-sqlite-first.md
    - docs/adr/ADR-0002-boot-config-pull-at-boot.md
    - docs/adr/ADR-0003-proxmox-acl-scoping.md
    - docs/adr/ADR-0004-static-ip-from-vmid.md
    - docs/adr/ADR-0005-clone-mode-full.md
    - docs/adr/ADR-0006-ttyd-persistent-drop-once.md
    - docs/adr/ADR-0007-ttyd-lan-bind.md
    - docs/adr/ADR-0008-stack-version-bumps.md
  modified: []

key-decisions:
  - "pull-at-boot (ADR-0002) chosen over SSH-to-node push (Option A) and API-only injection (Option C); the latter is impossible — no Proxmox HTTPS API writes a file into an LXC rootfs."
  - "Tight ACL scoping (ADR-0003): /pool/burrow-workers + /storage + /nodes over cluster-wide /vms; the consequence is the clone path must add each new VMID to the pool."
  - "ADR-0008 consolidates all eight stack bumps into one file (shared rationale, shared STACK.md 2026-06-09 evidence) rather than eight near-identical ADRs; records the tailwind.config.ts removal."

patterns-established:
  - "Every ADR opens with the <!-- --> two-line SPDX block header (Markdown comment syntax)."
  - "ADRs use placeholders only for topology (<node>, <rootfs-storage>, <subnet>, <bridge>, VMID) — never real hostnames/IPs/VMIDs."

requirements-completed: []

# Metrics
duration: 8min
completed: 2026-06-10
---

# Phase 0 Plan 05: Eight Nygard ADRs Summary

**The eight Phase-0 spec deviations are now recorded as Nygard-style ADRs in `docs/adr/` (sqlite-first, pull-at-boot, ACL scoping, static-IP-from-VMID, `--full` clone, persistent ttyd, ttyd LAN bind, and the consolidated stack-version bumps), each with a Status/Context/Decision/Consequences/Revisit-trigger body and the two-line SPDX block — satisfying the CONTRIBUTING.md "deviations need an ADR before merge" rule for the whole phase.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-06-10
- **Tasks:** 3
- **Files modified:** 8 created

## Accomplishments
- **ADR-0001 (sqlite-first):** SQLite via `aiosqlite` is the v1 store behind `DbProvider`; Postgres is an additive stub. Rationale lifted from tech-spec Appendix A.
- **ADR-0002 (boot-config pull-at-boot, HIGHEST PRIORITY):** records the load-bearing finding that `pct exec`/`pct push` are node-CLI-only and absent from the Proxmox HTTPS API (PROXMOX-PRIMING §1, SC-4), so `injectBootConfig` becomes a DB write and the worker fetches non-secret config + a short-lived git credential from `GET /api/v1/internal/bootconfig/{vmid}` at boot. Endpoint impl = Phase 1; pull step = Phase 3. Weighs Option A (SSH-push) and Option C (API-only, impossible).
- **ADR-0003 (proxmox-acl-scoping):** tight `/pool/burrow-workers` + `/storage/<rootfs>` + `/nodes/<node>` scoping over broad `/vms`, granted to both user and token (privsep intersection); consequence — the clone path must add each new VMID to the pool.
- **ADR-0004 (static-ip-from-vmid):** compute the IP from the VMID (unprivileged LXC has no guest agent; DHCP discovery is racey/unreliable); records the off-host DHCP-exclusion obligation (SC-6, PROXMOX-PRIMING §4).
- **ADR-0005 (clone-mode-full):** clone workers with `--full` on thin storage so ephemeral workers are template-independent and `destroy` frees space; budget clone time into the UPID wait, not the ttyd health timeout.
- **ADR-0006 (ttyd-persistent):** drop `--once` — tab close DETACHES, destroy is the only kill path (SC-8).
- **ADR-0007 (ttyd-lan-bind):** bind ttyd to the worker LAN interface, not `lo`, resolving the spec §9.3↔§6.4 contradiction (SC-9 / WORK-04); explicit security dimension (LAN boundary accepted under v1 LAN-only posture; never expose `:7681` beyond the LAN).
- **ADR-0008 (stack-version-bumps):** one consolidated ADR pinning Vite 8, TypeScript 6, Biome 2, Vitest 4, @xterm 6, mypy 2, react-mosaic-component 6.2.0 (NOT the 7.0.0-beta0 `latest` tag), and Tailwind v4 via `@tailwindcss/vite` with **no** `tailwind.config.ts`. Evidence base: STACK.md live registry reads 2026-06-09.

## Task Commits

Each task was committed atomically:

1. **Task 1: ADR-0001 + ADR-0002 + ADR-0003 (data store + boot-config + ACL scoping)** — docs
2. **Task 2: ADR-0004 + ADR-0005 + ADR-0006 + ADR-0007 (static-IP, clone, ttyd persistent, ttyd LAN bind)** — docs
3. **Task 3: ADR-0008 consolidated stack-version-bumps** — docs

(Commit hashes recorded in STATE.md after the metadata commit.)

## Files Created/Modified
- `docs/adr/ADR-0001-sqlite-first.md` — SQLite v1 store behind `DbProvider`
- `docs/adr/ADR-0002-boot-config-pull-at-boot.md` — pull-at-boot mechanism (highest priority)
- `docs/adr/ADR-0003-proxmox-acl-scoping.md` — tight pool/storage/node ACL scoping
- `docs/adr/ADR-0004-static-ip-from-vmid.md` — VMID→IP scheme + DHCP exclusion
- `docs/adr/ADR-0005-clone-mode-full.md` — `--full` clone on thin storage
- `docs/adr/ADR-0006-ttyd-persistent-drop-once.md` — drop `--once`; detach ≠ terminate
- `docs/adr/ADR-0007-ttyd-lan-bind.md` — ttyd LAN bind (WORK-04) + security dimension
- `docs/adr/ADR-0008-stack-version-bumps.md` — consolidated stack bumps (STACK.md evidence)

## Decisions Made
- **pull-at-boot over push** (ADR-0002): Option C (API-only file injection) is *impossible* — no Proxmox HTTPS API writes an arbitrary file into a CT rootfs (only `net0` is API-settable); Option A (restricted SSH + `pct push`) reintroduces a second root-gated trust channel and is reserved as a documented fallback only.
- **Tight ACL scoping** (ADR-0003) over cluster-wide `/vms`: fences a leaked token to Burrow's pool/storage/node at the cost of a pool-membership step in the clone path. `/vms` recorded as an explicit acceptable fallback.
- **One consolidated ADR-0008** instead of eight: the bumps share one rationale (spec `^` ranges are a major version behind stable) and one evidence base (STACK.md 2026-06-09), so a single file is the right granularity; `tailwind.config.ts` removal recorded as a config-shape consequence superseding spec §4.1.

## Deviations from Plan
None. All three tasks produced exactly the eight files named in `files_modified`, in the prescribed Nygard format with SPDX block headers and placeholders only.

## TDD Gate Compliance
N/A — this is a documentation-only plan (eight ADR Markdown files, no executable code). No test tier applies. Acceptance was verified by the plan's structural greps (see Verification).

## Verification
- SPDX block header present in all 8 ADRs (`<!-- -->` block, lines 1–4).
- `## Decision` and `## Consequences` sections present in all 8.
- Content checks pass: ADR-0002 contains `pct exec` + `bootconfig`; ADR-0003 contains `burrow-workers`; ADR-0007 contains `WORK-04` + LAN/interface; ADR-0008 contains `mypy`, `biome`, `react-mosaic`, and records `tailwind.config` removal.
- No topology leaks: `rg -niE 'pve1\.local|192\.168|10\.0\.0\.' docs/adr/` returns nothing — placeholders only.
- `uvx reuse lint` could not be run in this environment (the `reuse` wheel is missing its encoding-detection module — `NoEncodingModuleError`, a tooling-install gap unrelated to the ADRs). SPDX compliance was instead verified directly: every ADR carries the exact two-line block from CONTRIBUTING.md. Plan 00-04 owns the project-wide `REUSE.toml`/`.reuse` setup that makes `reuse lint` green.

## Issues Encountered
- `uvx reuse lint` fails to import (`NoEncodingModuleError`) on this host and, separately, `reuse lint` takes no path argument (it lints the whole project, which lacks the Plan-00-04 REUSE config). Neither affects the ADR files; SPDX headers were verified by inspection.

## Known Stubs
None. All eight ADRs are complete records. The decisions they freeze are *consumed* (not stubbed) by later plans: ADR-0002 by Phase 1's `injectBootConfig` + bootconfig endpoint and Phase 3's boot pull; ADR-0003/0004/0005 by the host-prime kit (00-06) and `ProxmoxComputeProvider.clone` (Phase 1); ADR-0006/0007 by `burrow-boot.sh` (00-07).

## User Setup Required
None — documentation only.

## Next Phase Readiness
- The frozen decisions are now auditable source-of-truth for the rest of Phase 0 and Phases 1/3. Plan 00-06 (host-prime kit) builds the ACL grants per ADR-0003 and the static-IP/DHCP-exclusion notes per ADR-0004. Plan 00-07 (golden template + `burrow-boot.sh`) implements persistent ttyd (ADR-0006) bound to the LAN interface (ADR-0007).
- WORK-04's **documentation half** is satisfied by ADR-0007; its implementation/validation half (ttyd actually reachable on the LAN from the proxy) lands with the boot script (00-07) and the dev-homelab smoke gate, so WORK-04 remains Pending in REQUIREMENTS traceability.

## Self-Check: PASSED

All eight ADR files verified present on disk with correct SPDX headers and Nygard structure; structural and content greps pass; no topology leaks.

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
