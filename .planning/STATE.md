---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Go Live
status: executing
stopped_at: Completed 10-02-PLAN.md (TEST-02 / 07r e2e hardening)
last_updated: "2026-06-25T10:15:37.818Z"
last_activity: 2026-06-25
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 4
  completed_plans: 2
  percent: 0
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-24)

**Core value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.
**Current focus:** Phase 10 — persistence-data-model-reaper-carve-out

## Current Position

Phase: 10 (persistence-data-model-reaper-carve-out) — EXECUTING
Plan: 3 of 4
Status: Ready to execute
Last activity: 2026-06-25

## Performance Metrics

**Velocity:**

- Total plans completed: 33
- Average duration: 16 min
- Total execution time: 3.50 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 7 | 137 min | 20 min |
| 1 | 5 | 75 min | 15 min |
| 5 | 4 | - | - |
| 6 | 1 | - | - |
| 7 | 1 | - | - |
| 8 | 2 | - | - |
| 9 | 3 | - | - |

**Per-plan:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 1 P03 | 11 min | 3 tasks | 8 files |
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
| Phase 1 P04 | 12 | 3 tasks | 14 files |
| Phase 1 P05 | 9 min | 3 tasks | 5 files |
| Phase 2 P01 | 14 min | 3 tasks | 8 files |
| Phase 2 P02 | 24 min | 3 tasks | 22 files |
| Phase 02 P03 | 16min | 3 tasks | 10 files |
| Phase 2 P04 | 23 | 2 tasks | 11 files |
| Phase 2 P05 | 51min | 3 tasks | 12 files |
| Phase 2 P06 | 35min | 2 tasks | 13 files |
| Phase 3 P01 | 22min | 3 tasks | 9 files |
| Phase 03 P02 | 38min | 2 tasks | 9 files |
| Phase 03 P03 | 9min | 2 tasks | 3 files |
| Phase 04 P02 | 38min | 3 tasks | 5 files |
| Phase 04 P03 | 12 | 3 tasks | 8 files |
| Phase 04 P04 | 41min | 2 tasks | 4 files |
| Phase 04 P01 | 12min | 3 tasks | 5 files |
| Phase 04 P05 | 18min | 1 task | 1 file |
| Phase 5 P01 | 16min | 3 tasks | 7 files |
| Phase 5 P02 | 14min | 3 tasks | 4 files |
| Phase 5 P03 | 9 | 2 tasks | 2 files |
| Phase 7 P01 | 10 | 2 tasks | 4 files |
| Phase 8 P08-01 | 12 | 3 tasks | 4 files |
| Phase 8 P08-02 | 5min | 3 tasks | 3 files |
| Phase 9 P09-01 | 18min | 2 tasks | 7 files |
| Phase 9 P09-02 | 20 | 2 tasks | 5 files |
| Phase 9 P09-03 | 7 min | 2 tasks tasks | 4 files files |
| Phase 10 P01 | 8 | 2 tasks | 2 files |
| Phase 10 P02 | 5 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap v1.3]: v1.3 = a 5-phase milestone continuing the numbering from v1.2 (Phase 10 persistence data model + reaper carve-out — `003` migration + negative-control reaper test + mocked-proxmoxer integration tier; Phase 11 scrollback restore — worker-side tmux in `cc-worker-config`; Phase 12 setup wizard backend — `testConnection`/`verifyTemplate` + `routers/setup.py`; Phase 13 setup wizard UI + first-run gate; Phase 14 first real-infra acceptance — operator human UAT). 15/15 requirements mapped, 0 unmapped, no requirement in two phases. Phases 10/12/13 are CI-provable over the Fake; Phase 11 is worker-side (CI-provable via the boot harness); **Phase 14 is human UAT on real infra (NOT CI-provable) — flagged so downstream planning treats it as acceptance, not code.** Followed the research-proposed breakdown verbatim — no coverage gap forced a deviation.
- [Roadmap v1.3]: Build order is a dependency chain — Phase 10 is the shared foundation (the `settings` singleton + `persistent` column + reaper carve-out + mocked-proxmoxer tier gate everything persistence/setup-touching). Phase 11 (worker-side, separate `cc-worker-config` repo, zero `api/`/`ui/` change) and Phase 12 (wizard backend) parallelize off Phase 10. Phase 13 (wizard UI) consumes Phase 12's endpoints + Phase 10's `persistent` column. Phase 14 (real-infra acceptance) builds LAST, gated on the wizard + persistence being real and CI-green. TEST-02 (07r e2e nit) is bundled into Phase 10 as test-hardening (no better home; it touches the same stop/start e2e suite Phase 10's persistence work exercises).
- [Roadmap v1.3]: Locked-at-definition decisions carried into the phases — persistence is **opt-in per workspace** (default ephemeral; Tier-1 plain `pct stop`/`start`, NO snapshots/CRIU); the reaper gets a **carve-out + negative-control regression test only** (no new auto-reaping code/TTL); the Proxmox token is **validate-in-memory, `.env`-only** (no secret-at-rest, no token-at-rest ADR). The reaper-destroys-a-persistent-workspace hazard (Pitfall #1) is a hard Phase-10 gate; the Fake-vs-real proxmoxer gap (Pitfall #2) is closed by the mocked-proxmoxer tier BEFORE any persistence-compute change.
- [Roadmap v1.3]: Anticipated ADRs (authored within their phase, `docs/adr/`) — ADR-0011 setup-state store (`settings` singleton + `setupCompletedAt`, Phase 10/12); ADR-0012 new `ComputeProvider` capabilities `testConnection`/`verifyTemplate` with Fake parity (Phase 12); ADR-0013 persistence model (Tier-1 `persistent` flag; snapshots/suspend deferred) (Phase 10); ADR-0014 tmux scrollback in the worker template (Phase 11). Token-at-rest ADR avoided by design.
- [Roadmap v1.2]: v1.2 = a 3-phase milestone continuing the numbering from v1.1 (Phase 7 backlog fixes — UI-12 fast-reconcile + CICD-09 e2e hardening, frontend/test; Phase 8 release hardening — RELX-01 release-please + RELX-02 harden-runner, CI config/docs; Phase 9 auto node selection — WSX-01 backend create-saga + a small create-modal UI touch). 5/5 requirements mapped, 0 unmapped. Every criterion is CI-provable over the Fake provider — no real-Proxmox path. ACC-01/02/03 (real-infra acceptance) + WSX-02/03 (real-boot v2) stay deferred Future Requirements, NOT phases.
- [Roadmap v1.2]: The three phases touch disjoint surfaces (Phase 7 the React app + e2e, Phase 8 `.github/workflows/` + docs, Phase 9 the API create-saga + one create-modal touch) so the inter-phase dependency edges are empty — numeric execution order is 7 → 8 → 9 but all three may be planned/executed in parallel. Phase 9 depends on the v1.0 Phase 1 create saga + Phase 2 create modal / `GET /api/v1/nodes`, not on Phase 7 or 8.
- [Roadmap v1.2]: RELX-01 is LOCKED to release-please (the PROJECT.md Open-Q "release-please vs semantic-release" is resolved — do not propose semantic-release in Phase 8). RELX-02 = `step-security/harden-runner` egress allowlist (audit-then-block) + all third-party actions SHA-pinned; resolves the PROJECT.md "harden-runner: adopt now or defer" open item by adopting it this milestone. WSX-01 node selection must read only the `ComputeProvider` capacity surface (node mem fraction / threshold) — no Proxmox specifics leak past the seam (seam-leakage guard stays green).
- [Roadmap v1.1]: v1.1 = a tight 2-phase polish milestone continuing the numbering from v1.0 (Phase 5 frontend stop/start + drawer polish; Phase 6 CI/tooling robustness). 7/7 requirements mapped, 0 unmapped. Every criterion is CI-provable over the Fake provider — no real-Proxmox path; the v1.0 acceptance debt (ACC-01/02/03) is excluded by design (needs real infra off the dev box).
- [Roadmap v1.1]: Phase 6 (CICD-07/08) has NO dependency on Phase 5 — it touches the CI workflow + tooling/docs only, not the React app — so it may be planned/executed in parallel; numeric execution order is 5 → 6 but the dependency edge is empty.
- [Roadmap v1.1]: Phase 5 builds entirely on the v1.0 surface — WS-06/WS-07 endpoints, the TanStack hooks, the activity drawer, and the four-theme token sheet (incl. `--accent-line`, verified present across all four themes in `docs/design/burrow-ui-mockup.html`) already ship. Stop/Start controls treat the backend state machine as the authority (mirrors the v1.0 SC-12 UI posture); detach-vs-destroy semantics are unchanged (close panel = detach, destroy is the only kill path).
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
- [Plan 00-07]: Golden-template shell artifacts authored from the SC-corrected RESEARCH skeletons, NOT the tech-spec §9.3 snippet (its --once and --interface lo are both SC-reversed). burrow-boot.sh ttyd is FROZEN: --port 7681 --writable --interface 0.0.0.0, NO --once (SC-8 persistent) + LAN bind (SC-9 / WORK-04). Pull-at-boot is a documented TODO(Phase 3) stub; no secret is written to /etc/burrow/worker.env (SC-4). WORK-01/WORK-04 script half done; real-template build/boot is the dev-homelab gate. **(v1.3 Phase 11 WSX-03 inserts `tmux new-session -A -s burrow` into this same FROZEN ttyd exec line — the only change to it since v1.0.)**
- [Plan 00-07]: Unit-location conflict resolved — burrow-worker.service canonicalized under cc-worker-config/systemd/ (Plan 00-07, most-recent-doc-wins) rather than worker-template/ where 00-06's 20-create-template.sh expected it; 20-create-template.sh's WORKER_UNIT repointed at the systemd/ path.
- [Plan 00-02]: ComputeProvider ABC exposes the COMPLETE Phase-1 saga method set + typed ComputeError hierarchy; the surface is frozen before the saga is written (PLAT-07, SC-13). **(v1.3 Phase 12 SETUP adds two NEW capabilities to this ABC — `testConnection`/`verifyTemplate` — with Fake parity, per ADR-0012.)**
- [Plan 00-02]: FakeComputeProvider is in-memory + deterministic (IP=10.99.0.<vmid%256>, no random/sleep), lifecycle-accurate, with an injectable FakeFailures(raise_on_nth_call) hook shaped for Phase-1 compensation tests (PLAT-08). **(v1.2 Phase 9 WSX-01 auto-select is proven over this Fake's multi-node getNodeMemory capacity — least-loaded-fitting chosen, over-threshold skipped, no-fit refuses. v1.3 Phase 10 adds a mocked-proxmoxer integration tier ALONGSIDE the Fake to close the structural error/UPID-path gap the Fake never triggers.)**
- [Plan 00-02]: Scoped mypy override module='proxmoxer.*' ignore_missing_imports (no py.typed) keeps --strict on all first-party code; proxmoxer stays confined to proxmoxProvider.py.
- [Plan 00-02]: SQLite columns are camelCase (tech-spec §7.1 verbatim); snake<->camel bridge lives ONLY in sqliteProvider.py. 001_init.sql omits the UNIQUE(vmid) partial index (Phase-1 002_* migration, SC-4). **(v1.3 Phase 10 adds a `003` migration — a singleton `settings` table + a `persistent` column on workspaces — through the same ordered ledger.)**
- [Phase ?]: Plan 01-04: /api/v1 thin routers (workspaces CRUD + stop/start/destroy/events, templates, degrade-not-500 health) wired via get_service DI; ServiceError/.code + ComputeError mapped to envelope statuses (409/404/502). JSON logging (stdlib JsonFormatter, extra-key whitelist, no secrets), SecurityHeadersMiddleware (4 headers, no HSTS), non-* CORS from Settings (outermost). get_compute is a process-wide singleton so the Fake state survives across requests (Rule 1); DbProvider.listTemplates added (Rule 2). Integration tier (ASGITransport + real temp SQLite + Fake + respx stub-ttyd) proves CRUD/health/security. **(v1.3 Phase 12 adds a `/api/v1/setup/*` router via this same get_service DI + envelope mapping; the wizard health step REUSES this degrade-not-500 /api/v1/health.)**
- [Plan 01-03]: lib/statemachine.py is the policy authority — a single TRANSITIONS table + assert_transition called BEFORE every stop/start/destroy mutation; creating is internal-only (never an action target) and error exits only via destroy (A4). **(v1.3 Phase 10 WSX-02 reuses the existing `stopped` state + `stopCt`/`startCt` for persistence — NO new state, NO ComputeProvider ABC change for Tier 1; the reconciler/auto-stop must treat a `persistent` stopped workspace as durable.)**
- [Phase 04]: [Plan 04-01]: Reconciler (reaper + idle auto-stop, CAP-02/CAP-03) is one pure `reconcile_once()` over the two seams with an INJECTABLE `now`; `_reap` destroys in-pool CTs with no live DB row under the load-bearing `if vmid in pool` bound; timed-out `creating` rows get destroyCt + status=error. **(v1.3 Phase 10 WSX-04 hard gate: VERIFY this `_reap` predicate keys on "no owning DB row," NOT on `stopped` state, and LOCK it with a negative-control regression test proving a persistent stopped workspace is never reaped — Pitfall #1.)**
- [Phase 04]: [Plan 04-05]: Release supply-chain workflow (CICD-05). `.github/workflows/release.yml` on `v*` tag / release published: one `publish` job with EXACTLY `contents:read + packages:write + id-token:write + attestations:write` over a two-image matrix; cosign keyless + SLSA attestation, every step bound `@<digest>`. **(v1.3 Phase 14 ACC-03 is the FIRST real exercise of this path — real GHCR push + `cosign verify` + `gh attestation verify` against the published `@sha256:` digest; verify by digest not tag, exactly 4 publish perms.)**
- [Phase 8]: [Plan 08-02]: harden-runner (audit) is the literal step 0 of all four CI/release jobs; every `uses:` across all three workflows (25 refs) is a 40-hex commit SHA. **(v1.3 Phase 14 ACC-02 flips harden-runner egress `audit`→`block` with the discovered allowlist + lands the first live release-please PR; pre-seed Fulcio/Rekor/TUF in the allowlist.)**
- [Phase 9]: [Plan 09-03]: NewWorkspaceModal defaults to an Auto (least-loaded) <option value=""> and submits node: null; isValid drops the node requirement. **(v1.3 Phase 13 adds a `persistent` checkbox onto this SAME modal — default unchecked = ephemeral — completing the UI half of WSX-02 against the Phase 10 backend.)**
- [Phase ?]: [Plan 10-01]: TEST-01 hard gate GREEN — mocked-proxmoxer integration tier (api/tests/integration/mock_proxmox.py factories + test_mock_proxmox.py self-tests) drives the REAL ProxmoxComputeProvider through running->stopped UPID polling + ResourceException 404/500 inspector branches the Fake never triggers. responses (NOT respx); 9-segment UPID via make_upid; ResourceException raised via responses body=<exc> to hit _is_not_found/_is_running_or_locked exactly. Unblocks persistence-compute Plans 03/04.
- [Phase ?]: [Plan 10-02]: TEST-02 / 07r e2e hardening landed in ui/tests/e2e/stop-start.spec.ts. W2: the afterEach now captures the cleanup request.delete and asserts expect([200,404]).toContain(res.status()) so a swallowed teardown fails loudly at root cause instead of leaking Fake state as a downstream flaky order-dependent failure (RESEARCH Pitfall 6); cleanup stays id-scoped over createdIds (no broad wipe). W3: the round-trip asserts toHaveCount(2) over the two Start affordances (header button TerminalPanel.tsx:374-383 + placeholder CTA :461-476) and the placeholder CTA visible in the role=status region, BEFORE the unchanged strict-mode placeholder-scoped Start CLICK. W1 id-tracking + unique-per-run names untouched; suite green 5/5. Test-only edit, independent of the Phase-10 api/persistence plans.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

- 07r-harden-stop-start-e2e-cleanup (ui/e2e) — 3 Phase-7 review warnings, e2e cleanup robustness. **CLAIMED by v1.3 Phase 10 (TEST-02).**
- 2026-06-18-support-multiple-ai-coding-agents-in-workers (general) — boot Cursor / GitHub Copilot / Codex in workers, not just Claude Code. **Deferred to v1.4 (research-first); stays unlinked in .planning/todos/pending/.**

### Blockers/Concerns

[Issues that affect future work]

- ADRs required before/within their phase: **Phase 0 — RESOLVED (Plan 00-05):** all eight v1.0 deviation ADRs authored (ADR-0001..0008). **Phase 3 — RESOLVED (Plan 03-03):** B4 plugin cadence → ADR-0009. **Phase 4 — RESOLVED:** in-process reconciler + capacity lock → ADR-0010. **v1.1/v1.2:** no baseline-architecture deviation emerged. **v1.3 — FOUR ADRs anticipated:** ADR-0011 setup-state store (Phase 10/12), ADR-0012 new ComputeProvider caps testConnection/verifyTemplate (Phase 12), ADR-0013 persistence model Tier-1 persistent flag (Phase 10), ADR-0014 tmux scrollback (Phase 11) — author each within its phase. Token-at-rest ADR avoided by design.
- Real-infra-only validation: Phase 0 template, Phase 1 real-clone create, Phase 3 worker boot cannot be CI-verified — dev-homelab smoke gate is the acceptance authority. **v1.3 — Phase 14 is the milestone's explicit real-infra acceptance phase (ACC-01/02/03): human UAT on real Proxmox + the first live GHCR/cosign release. It is NOT CI-provable by design — downstream planning must treat it as acceptance/runbook, not feature code. Host-prime prerequisites (worker-pool storage type, privsep ACL depth, `VM.Snapshot` not needed for Tier-1) must be operator-confirmed before the Phase 14 smoke.**
- v1.3 hard gates (from research PITFALLS): (1) reaper-destroys-a-persistent-workspace hazard → Phase 10 negative-control regression test (hard gate); (2) Fake-vs-real proxmoxer structural gap → Phase 10 mocked-proxmoxer integration tier landed BEFORE any persistence-compute change; (3) wizard is a new ingress for the powerful PVE token → Phase 12 write-only/redacted/never-round-tripped; (4) first cosign/GHCR release traps → Phase 14 runbook (verify by digest, exactly 4 publish perms, gh attestation verify can exit-0-on-failure so assert on output, harden-runner block-flip must pre-seed Fulcio/Rekor/TUF).

## Deferred Items

Items acknowledged and deferred at the v1.0/v1.1 milestone closes (all by-design real-infra
acceptances — CI never touches real Proxmox; see the milestone audits + each phase's
*-HUMAN-UAT.md). The v1.1 backlog rows were claimed by v1.2; the v1.2-deferred real-infra +
real-boot-v2 rows are now CLAIMED by v1.3.

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| uat_gap | Phase 03 — 03-HUMAN-UAT.md (real worker boot + plugin load smoke) | **claimed by v1.3 Phase 14 (ACC-01)** | 2026-06-11 |
| uat_gap | Phase 04 — 04-HUMAN-UAT.md (real reaper/auto-stop/capacity + GHCR publish/cosign verify) | **claimed by v1.3 Phase 14 (ACC-01/03)** | 2026-06-11 |
| verification_gap | Phase 01 — 01-VERIFICATION.md (human_needed; CI-provable saga passed, real Proxmox = smoke) | **claimed by v1.3 Phase 14 (ACC-01)** | 2026-06-11 |
| verification_gap | Phases 00/02/04 — human_needed (CI-provable contracts passed; real-infra = dev-homelab smoke) | **claimed by v1.3 Phase 14 (ACC-01/02)** | 2026-06-11 |
| backlog | WR-01 — LeafPanel onTerminalEvent fast-reconcile wiring | claimed by v1.2 Phase 7 (UI-12) — DONE | 2026-06-15 |
| backlog | WR-02 — stop/start e2e hardening (scoped locators + per-test isolation) | claimed by v1.2 Phase 7 (CICD-09) — DONE | 2026-06-15 |
| backlog | 07r — stop/start e2e cleanup robustness (W1/W2/W3) | **claimed by v1.3 Phase 10 (TEST-02)** | 2026-06-16 |
| release | First real CI run on a live runner (pinned reuse + harden-runner + release-please PR) | **claimed by v1.3 Phase 14 (ACC-02)** | 2026-06-15 |
| release | Real GHCR release (publish + cosign verify + gh attestation verify) | **claimed by v1.3 Phase 14 (ACC-03)** | 2026-06-11 |
| v2 | WSX-02 persistent workspaces (Tier-1 stop/start) | **claimed by v1.3 Phase 10 + 13** | 2026-06-15 |
| v2 | WSX-03 full scrollback restore (tmux in the worker) | **claimed by v1.3 Phase 11** | 2026-06-15 |
| v2 | WSX-05/06/07 snapshots / CRIU suspend / cross-reboot scrollback | deferred to v1.4+ (storage + VM.Snapshot priv + CRIU limits) | 2026-06-24 |
| milestone | AGENT-01+ multi-agent workers (Cursor / Copilot / Codex) | deferred to v1.4 (research-first; todo unlinked) | 2026-06-24 |

## Session Continuity

Last session: 2026-06-25T10:15:37.810Z
Stopped at: Completed 10-02-PLAN.md (TEST-02 / 07r e2e hardening)
Resume file: None
Next plan: Plan Phase 10 with `/gsd:plan-phase 10` (Persistence Data Model + Reaper Carve-out — the v1.3 foundation: `003` migration + reaper negative-control test + mocked-proxmoxer integration tier). Phase 11 (scrollback, worker-side) and Phase 12 (wizard backend) parallelize off Phase 10.

## Operator Next Steps

- Review the v1.3 roadmap (`.planning/ROADMAP.md`), then plan Phase 10 with `/gsd:plan-phase 10`.
