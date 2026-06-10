---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Completed 01-02-PLAN.md (real ProxmoxComputeProvider: UPID-blocked clone/start/stop/destroy in asyncio.to_thread, CA-pinned TLS, net0 static IP + pool-add, node memory; responses-mocked CI proof; PLAT-07/CAP-01/CICD-02/03)"
last_updated: "2026-06-10T15:44:23.229Z"
last_activity: 2026-06-10
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 12
  completed_plans: 9
  percent: 20
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-09)

**Core value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.
**Current focus:** Phase 1 — Control Plane API

## Current Position

Phase: 1 of 4 (Control Plane API)
Plan: 2 of 5 complete in current phase
Status: Executing Phase 1
Last activity: 2026-06-10 — Plan 01-02 complete: the frozen Phase-0 `ProxmoxComputeProvider` skeleton filled with real `proxmoxer` bodies behind the ABC (PLAT-07). Every mutating call (clone/start/stop/destroy) returns a Proxmox UPID and is blocked on via `Tasks.blocking_status` (assert `exitstatus == "OK"`) before returning (SC-1); every blocking `proxmoxer` call runs in `asyncio.to_thread` so no synchronous call stalls the event loop (Pitfall 2). `cloneCt` does a `--full` clone, adds the new VMID to `/pool/burrow-workers` (ADR-0003), and sets the static `net0` IP from the VMID (ADR-0004), then blocks on the clone UPID; proxmoxer request errors map to typed `CloneError`. `getNodeMemory` returns the `mem/maxmem` fraction (CAP-01 data source); `getIp` computes the address from the VMID (ADR-0004, SC-6 — no DHCP/agent poll); `destroyCt` of an absent CT is an idempotent no-op success (compensation-safe). CA-pinned TLS via `verify_ssl=proxmox_ca_cert_path` — verification never disabled (block_on=high gate; comment-stripped grep returns 0). All `proxmoxer` symbols stay confined to `proxmoxProvider.py` (seam guard green). `responses` + `respx` added as dev deps; a `responses`-mocked integration test proves UPID-block + pool-add PUT + net0 PUT + node-memory + the non-OK/timeout failure paths hermetically. Real-Proxmox clone/boot acceptance is the deferred dev-homelab smoke gate (no Proxmox reachable). Full gate green: 45 pytest passed, ruff + ruff format + mypy --strict (29 files) + uv lock --check + reuse lint (125/125).

Progress: [████░░░░░░] 40% (Phase 1: 2/5 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 9
- Average duration: 19 min
- Total execution time: 2.52 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 5 | 86 min | 17 min |
| 1 | 2 | 43 min | 22 min |

**Per-plan:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 1 P01 | 22 min | 4 tasks | 8 files |
| Phase 0 P06 | 35 min | 4 tasks | 7 files |
| Phase 0 P07 | 20 min | 3 tasks | 4 files |
| Phase 0 P02 | 11 min | 3 tasks | 10 files |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 0 P04 | 20 min | 3 tasks | 22 files |
| Phase 0 P03 | 18 min | 3 tasks | 9 files |
| Phase 01 P02 | 21min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Plan 01-01]: 002 partial unique index on `workspaces(vmid) WHERE deletedAt IS NULL AND vmid IS NOT NULL` is the cross-process VMID reservation arbiter (SC-3/SC-4); soft-deleted tombstones and NULL vmids stay out of the index so destroy-then-recreate reuses a vmid. A plain UNIQUE would break recycle.
- [Plan 01-01]: `migrate()` is now an ordered, idempotent `schema_migrations`-ledger runner applying every `migrations/*.sql` by stem — replaces the Phase-0 "skip if workspaces table exists" check that wrongly skipped 002 on an existing DB (Pitfall 6).
- [Plan 01-01]: `VmidTakenError` is discriminated on the SQLite `workspaces.vmid` column phrase, NOT the index name — SQLite reports the violated column for a partial-unique failure, and the 002 index is the only uniqueness on that column. Declared on the DbProvider ABC module so the service catches it without an aiosqlite dep.
- [Plan 01-01]: `getEvents` orders by `(createdAt, rowid)` so two same-millisecond events keep insertion order (deterministic WS-11 oldest-first). `getByVmid` returns the active (non-soft-deleted) vmid owner.
- [Plan 01-01]: All Phase-1 `Settings` keys consolidated in one config.py edit (single-owner file → no cross-plan write conflicts) with safe non-secret placeholder defaults; real LAN/secret values live only in the gitignored `.env` (T-01-22 mitigation).
- [Roadmap]: Seams-first build — provider ABCs + FakeComputeProvider + envelope land in Phase 0 so ~80% of the backend is CI-green before any real Proxmox call.
- [Roadmap]: Implement the Spec Corrections (SC-1..SC-13), not the spec happy-path — UPID waits, persist-before-clone, race-safe VMID reservation, partial unique index, `tty` subprotocol, persistent ttyd.
- [Phase 0]: Drop ttyd `--once` (SC-8), bind ttyd to the worker LAN interface (SC-9), use `--full` clone — frozen before the template is finalized.
- [Phase 0]: Proxmox priming is a one-time operator kit (`cc-worker-config/lxc/host-prime/` + `PRIMING.md`); least-priv `burrow@pve` role (9 privs) + privsep token scoped to pool/storage/node. See SETUP-01..05 and `research/PROXMOX-PRIMING.md`.
- [Phase 0→1]: Boot config delivered pull-at-boot (recommended) — `pct exec`/`pct push` are not in the HTTPS API; `injectBootConfig` = DB write + worker fetch from an internal endpoint. WORK-03 reframed; mechanism locked by Phase 0 ADR.
- [Plan 00-01]: Provider switches bind via `Field(validation_alias="BURROW_COMPUTE"/"BURROW_DB")` — a bare field would bind the lowercase env name, not the BURROW_* name (verified with `BURROW_COMPUTE=proxmox`).
- [Plan 00-01]: Single `CamelModel` base (`alias_generator=to_camel`, `populate_by_name`, `from_attributes`) is the sole snake↔camel mechanism; serialize at the boundary with `model_dump(by_alias=True)`. No per-field hand-mapping.
- [Plan 00-01]: Dev deps use PEP 735 `[dependency-groups]` (portable) over uv-specific `[tool.uv] dev-dependencies`.
- [Plan 00-05]: All eight Phase-0 ADRs authored (`docs/adr/ADR-0001..0008`). ADR-0002 locks **pull-at-boot** (Option C — API-only file injection — is impossible; no Proxmox HTTPS API writes a file into a CT rootfs; Option A SSH+`pct push` reserved as a documented fallback). ADR-0003 locks **tight ACL scoping** (`/pool/burrow-workers`+`/storage`+`/nodes`) with the consequence that the clone path must add each new VMID to the pool. ADR-0008 consolidates the stack bumps and records the `tailwind.config.ts` removal (Tailwind v4 is CSS-first via `@tailwindcss/vite`).
- [Plan 00-05]: ADR-0007 satisfies WORK-04's **documentation half** (ttyd LAN bind, security dimension recorded); the implementation/validation half lands with `burrow-boot.sh` (00-07) + dev-homelab smoke, so WORK-04 stays Pending.
- [Plan 00-06]: Host-prime kit authored (cc-worker-config/lxc/host-prime/ + PRIMING.md). BurrowProvisioner = exactly 9 privs; privsep token granted to BOTH user and token at pool/template/storage/node (effective = user-intersect-token); token captured silently, never echoed/CLI-arged, .env write refused unless git check-ignore passes (0600). SETUP-01..05 doc/script half complete; real-Proxmox acceptance deferred to dev-homelab smoke.
- [Plan 00-06]: shellcheck unavailable on the Windows dev host -> scripts validated with bash -n (all pass); shellcheck static analysis unverified, run in CI/homelab. SPDX verified via uvx --with charset-normalizer reuse lint-file.
- [Plan 00-07]: Golden-template shell artifacts authored from the SC-corrected RESEARCH skeletons, NOT the tech-spec §9.3 snippet (its --once and --interface lo are both SC-reversed). burrow-boot.sh ttyd is FROZEN: --port 7681 --writable --interface 0.0.0.0, NO --once (SC-8 persistent) + LAN bind (SC-9 / WORK-04). Pull-at-boot is a documented TODO(Phase 3) stub; no secret is written to /etc/burrow/worker.env (SC-4). WORK-01/WORK-04 script half done; real-template build/boot is the dev-homelab gate.
- [Plan 00-07]: Unit-location conflict resolved — burrow-worker.service canonicalized under cc-worker-config/systemd/ (Plan 00-07, most-recent-doc-wins) rather than worker-template/ where 00-06's 20-create-template.sh expected it; 20-create-template.sh's WORKER_UNIT repointed at the systemd/ path.
- [Plan 00-02]: ComputeProvider ABC exposes the COMPLETE Phase-1 saga method set + typed ComputeError hierarchy; the surface is frozen before the saga is written (PLAT-07, SC-13).
- [Plan 00-02]: FakeComputeProvider is in-memory + deterministic (IP=10.99.0.<vmid%256>, no random/sleep), lifecycle-accurate, with an injectable FakeFailures(raise_on_nth_call) hook shaped for Phase-1 compensation tests (PLAT-08).
- [Plan 00-02]: Scoped mypy override module='proxmoxer.*' ignore_missing_imports (no py.typed) keeps --strict on all first-party code; proxmoxer stays confined to proxmoxProvider.py.
- [Plan 00-02]: SQLite columns are camelCase (tech-spec §7.1 verbatim); snake<->camel bridge lives ONLY in sqliteProvider.py. 001_init.sql omits the UNIQUE(vmid) partial index (Phase-1 002_* migration, SC-4).
- [Phase ?]: [Plan 00-04]: Tier-0 static-gates CI job (CICD-01) runs ruff lint+format, mypy --strict, uv lock --check (api/), tsc --noEmit + biome ci (ui/), uvx reuse lint (repo); third-party actions SHA-pinned (checkout v4.3.1, setup-uv v6.8.0, setup-node v4.4.0), contents:read. PR-title gate via amannn/action-semantic-pull-request with placeholder SHA + '# TODO pin exact SHA' (exact pin deferred).
- [Phase ?]: [Plan 00-04]: REUSE/SPDX green repo-wide (CICD-06, 100/100) via LICENSES/AGPL-3.0-or-later.txt + REUSE.toml scoped to non-headerable files ONLY (uv.lock, package-lock.json, comment-less JSON, design/Burrow-handoff bundle) -- never blanket-globs source extensions so a missing inline header still fails. Headerable sources got inline headers; in-body example SPDX strings wrapped in REUSE-IgnoreStart/End.
- [Phase ?]: [Plan 00-04]: ui/ scaffold minimal-by-design (typescript@6.0.3 + @biomejs/biome@2.4.16 only); full UI tree is Phase 2. biome.json written fresh from biome init (2.4.16 schema); vcs.useIgnoreFile=false, includes scoped to src/**.
- [Phase ?]: [Plan 00-03]: App factory is the lone composition root — get_compute()/get_db() in main.py are the ONLY place concrete impls are named; BURROW_COMPUTE/BURROW_DB flip the backend with no service edit (both branches verified at runtime).
- [Phase ?]: [Plan 00-03]: Envelope shipped this phase as an ASGI error boundary only (Exception -> respond_error); success-wrapping middleware + routers are Phase 1 per plan.
- [Phase ?]: [Plan 00-03]: Seam-leakage guard uses Python tokenize to drop COMMENT + STRING tokens so seam-contract prose in docstrings is exempt while real driver usage is caught; negative-tested red on an injected leak, green on the tree (PLAT-06/07).
- [Phase ?]: [Plan 01-02]: ProxmoxComputeProvider blocks on every UPID via Tasks.blocking_status (assert exitstatus OK) before returning (SC-1); each proxmoxer call wrapped in asyncio.to_thread so no sync call runs on the event loop (Pitfall 2).
- [Phase ?]: [Plan 01-02]: cloneCt adds the new VMID to /pool/burrow-workers (ADR-0003) and sets net0 static IP from the VMID (ADR-0004) before blocking on the clone UPID; CA-pinned TLS via verify_ssl=proxmox_ca_cert_path, verification never disabled (block_on=high).
- [Phase ?]: [Plan 01-02]: proxmoxer's requests leg is mocked with responses (NOT respx, which is httpx-only); respx reserved for the httpx ttyd-health leg in Plan 04. destroyCt is idempotent (404 -> no-op success) for compensation safety.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- ADRs required before/within their phase: **Phase 0 — RESOLVED (Plan 00-05):** SC-8 (`--once`) → ADR-0006, SC-9 (ttyd binding) → ADR-0007, clone-mode `--full` → ADR-0005, boot-config injection (pull-at-boot) → ADR-0002, Proxmox ACL scoping (`/pool` vs `/vms`) → ADR-0003, static-IP-from-VMID → ADR-0004, sqlite-first → ADR-0001, stack-version bumps (Vite 8, TS 6, Biome 2, Vitest 4, @xterm 6, mypy 2, react-mosaic 6.2.0, Tailwind v4) → ADR-0008. **Still pending: Phase 3** — B4 plugin cadence (boot-time-latest vs snapshot-at-create).
- Real-infra-only validation: Phase 0 template, Phase 1 real-clone create, Phase 3 worker boot cannot be CI-verified — dev-homelab smoke gate is the acceptance authority (the "Looks Done But Isn't" checklist).

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-10T15:42:51.943Z
Stopped at: Completed 01-02-PLAN.md (real ProxmoxComputeProvider: UPID-blocked clone/start/stop/destroy in asyncio.to_thread, CA-pinned TLS, net0 static IP + pool-add, node memory; responses-mocked CI proof; PLAT-07/CAP-01/CICD-02/03)
Resume file: None
Next plan: 01-03-PLAN.md (WorkspaceService create/stop/start/destroy saga — persist-before-clone, per-step reverse compensation, state machine, capacity guard over the now-real ComputeProvider; reserves VMIDs through the 002 index + VmidTakenError from 01-01, calls the UPID-blocked clone/start/stop/destroy + getNodeMemory + getIp from 01-02). 01-04 (routers) reads events via getEvents; 01-05 (bootconfig) looks up workspaces via getByVmid.
