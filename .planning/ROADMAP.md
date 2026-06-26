<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)
- ✅ **v1.1 UI Polish + Stop/Start Controls** — Phases 5-6 (shipped 2026-06-15)
- ✅ **v1.2 Backlog Fixes + Release Automation** — Phases 7-9 (shipped 2026-06-16)
- 🚧 **v1.3 Go Live** — Phases 10-14 (active; guided setup wizard + opt-in persistence + scrollback restore + first real-infra acceptance)

Shipped milestone detail is archived per version in `milestones/`:
[`v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md),
[`v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md),
[`v1.2-ROADMAP.md`](milestones/v1.2-ROADMAP.md). Requirements + close-out audits live
alongside each. Start the next milestone with `/gsd:new-milestone`.

## Phases

**Phase Numbering:**

- Integer phases (7, 8, 9, 10): planned milestone work (each milestone continues the numbering)
- Decimal phases (7.1, 7.2): urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 MVP (Phases 0-4) — SHIPPED 2026-06-11</summary>

- [x] Phase 0: Contracts, Seams & Golden Template (7/7 plans) — completed 2026-06-10
- [x] Phase 1: Control Plane API (5/5 plans) — completed 2026-06-10
- [x] Phase 2: Terminal Proxy + React UI (6/6 plans) — completed 2026-06-10
- [x] Phase 3: Reproducible Workers (3/3 plans) — completed 2026-06-11
- [x] Phase 4: Hardening & Release (5/5 plans) — completed 2026-06-11

**Delivered:** a browser-accessible manager for many concurrent Claude Code sessions —
create→boot→live-terminal over both providers (Fake for CI, Proxmox for the homelab), a tiling
xterm/react-mosaic UI with reconnect + restore, reproducible manifest-driven workers with
credential hygiene, an in-process reaper + idle auto-stop + atomic capacity guard, a per-workspace
activity drawer, and a signed/attested/scanned container release path to GHCR. 26 plans; all
CI-provable contracts green over the Fake provider.

**Deferred to the dev-homelab smoke / first CI run / a real GHCR release** (CI never touches real
Proxmox by design — every phase closed `human_needed`): golden-template + real worker boot, real
reaper/auto-stop/capacity acceptance, image build+Trivy on the runner, and a real GHCR publish +
cosign/attestation verify. Tracked per-phase in `*-HUMAN-UAT.md` and in the close-out audit's
`tech_debt`.

</details>

<details>
<summary>✅ v1.1 UI Polish + Stop/Start Controls (Phases 5-6) — SHIPPED 2026-06-15</summary>

- [x] Phase 5: Stop/Start Controls + Drawer Polish (4/4 plans) — completed 2026-06-14
- [x] Phase 6: CI / Tooling Robustness (1/1 plan) — completed 2026-06-15

**Delivered:** explicit, state-machine-gated Stop/Start controls in the workspace UI
(UI-07/UI-08) with a calm `Workspace stopped` placeholder + Start CTA and no optimistic flip
(server-truth poll); the three 04-UI-REVIEW drawer-polish details restored as global CSS
(UI-09 phone full-width sheet via a `--w-drawer` token, UI-10 global `--accent-line`
`:focus-visible` ring, UI-11 custom Burrow scrollbar) across all four themes; and the CI/tooling
robustness fixes (CICD-07 `reuse` pinned to `--with charset-normalizer`; CICD-08 planning
artifacts licensed via REUSE.toml so PLAN frontmatter stays line-1 for the gsd-sdk parser).
5 plans; vitest 113/113 + Playwright e2e 7/7 green over the Fake provider; UI audit 23/24;
`reuse lint` compliant 309/309.

**Deferred (tech_debt, tracked):** WR-01 (LeafPanel fast-reconcile wiring) + WR-02 (e2e
hardening) as backlog todos; first real CI run on a live runner (ACC-02); the carried-forward
v1.0 real-infra acceptance (ACC-01/02/03). See `milestones/v1.1-MILESTONE-AUDIT.md`.

</details>

<details>
<summary>✅ v1.2 Backlog Fixes + Release Automation (Phases 7-9) — SHIPPED 2026-06-16</summary>

- [x] Phase 7: Backlog Fixes (Fast-Reconcile + E2E Hardening) (1/1 plan) — completed 2026-06-15
- [x] Phase 8: Release Hardening (release-please + harden-runner) (2/2 plans) — completed 2026-06-15
- [x] Phase 9: Auto Node Selection (3/3 plans) — completed 2026-06-16

**Delivered:** the two deferred v1.1 code-review findings closed (UI-12 `LeafPanel
onTerminalEvent` fast-reconcile + CICD-09 panel-scoped stop/start e2e hardening); a release-please
manifest-mode surface (config + manifest seeded 1.1.0 so the first PR proposes v1.2.0, push:main →
release PR → `v*` tag → existing publish) with `step-security/harden-runner` audit step 0 on all 5
CI/release jobs and every `uses:` SHA-pinned to a live-verified upstream commit (RELX-01/RELX-02);
and capacity-aware auto node selection (WSX-01) — `createWorkspace` auto-picks the least-loaded
fitting node via `selectNode` inside `_create_lock` over a `worker_nodes` Settings list and the
shared `_fits` comparator, manual pick unchanged, no-fit refuses with `capacity_exceeded`, modal
defaults to "Auto (least-loaded)". 6 plans; api 202 + ui 117 green, seam-leakage green, every v1.2
requirement CI-provable over the FakeComputeProvider.

**Deferred (real-infra / backlog, tracked):** ACC-01 (dev-homelab smoke incl. real multi-node
auto-select), ACC-02 (first live release-please PR + egress block-flip + full actionlint), ACC-03
(real GHCR publish + cosign/attestation verify), WSX-02/WSX-03 (persistent workspaces + scrollback
restore, real-boot v2), and the 07r e2e-cleanup-robustness nit. See
`milestones/v1.2-MILESTONE-AUDIT.md`.

</details>

### 🚧 v1.3 Go Live (Phases 10-14) — ACTIVE

**Milestone goal:** take Burrow from CI-proven-over-Fake to actually running on the operator's
real Proxmox — a guided in-app setup wizard, opt-in workspaces that persist across stop/start with
restored scrollback, and the first real-infra acceptance run (real create→terminal→stop→start→destroy,
first live release-please PR + egress block-flip, first real GHCR publish + cosign/attestation verify).

**Shape:** small in code, large in verification. Phases 10, 12, 13 are CI-provable over the
FakeComputeProvider; Phase 11 is worker-side (separate `cc-worker-config` repo, CI-provable via the
hermetic boot harness); Phase 14 is operator-run human UAT on real hardware (acceptance, not code).
Grounded in `.planning/research/SUMMARY.md`. Locked decisions: persistence is opt-in per workspace
(default ephemeral); the reaper gets a carve-out + regression test only (no new auto-reaping); the
Proxmox token is validate-in-memory, `.env`-only (no secret-at-rest).

- [x] **Phase 10: Persistence Data Model + Reaper Carve-out** — `003` migration (`settings` singleton + `persistent` column), reaper-never-reaps-a-persistent-stopped-workspace negative-control test, mocked-proxmoxer integration tier (CI-provable) (completed 2026-06-25)
- [x] **Phase 11: Scrollback Restore** — worker-side tmux `new-session -A` in `burrow-boot.sh` + baked `/etc/tmux.conf` so scrollback survives stop→start (worker-side, CI-provable via the boot harness) (completed 2026-06-25)
- [x] **Phase 12: Setup Wizard Backend** — `testConnection`/`verifyTemplate` on both providers, `routers/setup.py` + `SetupService`, token hygiene (CI-provable) (completed 2026-06-26)
- [x] **Phase 13: Setup Wizard UI + First-Run Gate** — `SetupWizard.tsx`, `App.tsx` first-run gate off `setupCompletedAt`, `persistent` checkbox in `NewWorkspaceModal` (CI-provable) (completed 2026-06-26)
- [ ] **Phase 14: First Real-Infra Acceptance** — operator-run human UAT on real Proxmox + first live GHCR/cosign release (human UAT, not CI)

**Anticipated ADRs** (Nygard style, authored within their phase, `docs/adr/`): ADR-0011 setup-state
store (`settings` singleton + `setupCompletedAt`) · ADR-0012 new `ComputeProvider` capabilities
(`testConnection`/`verifyTemplate`, Fake parity) · ADR-0013 persistence model (Tier-1 `persistent`
flag over stop/start; snapshots/suspend explicitly deferred) · ADR-0014 tmux scrollback in the
worker template. *Token-at-rest ADR avoided by design (`.env`-only, validate-in-memory).*

## Phase Details

### Phase 10: Persistence Data Model + Reaper Carve-out

**Goal**: A workspace can be marked persistent at create time and durably survive stop→start, the orphan reaper provably never destroys a persistent stopped workspace, and the structural Fake-vs-real proxmoxer gap is closed by a mocked-proxmoxer integration tier — the shared foundation everything persistence-touching builds on.
**Depends on**: Nothing new (builds on the v1.0 schema + migrations ledger, the `stopped` state + `stopCt`/`startCt`, and the in-process reconciler/reaper)
**Requirements**: WSX-02, WSX-04, TEST-01, TEST-02
**CI-provable**: yes — over the FakeComputeProvider + the new mocked-proxmoxer integration tier; no real Proxmox
**Success Criteria** (what must be TRUE):

  1. A `003` migration adds a singleton `settings` table and a `persistent` column on `workspaces`; `migrate()` applies it through the ordered ledger, and a fresh DB and a v1.2 DB both converge to the same schema.
  2. Creating a workspace with `persistent=true` then stop→start leaves the same DB row (not soft-deleted, same id/vmid) in `running` with its disk intact; the default create stays ephemeral.
  3. A negative-control regression test proves the orphan reaper never destroys a persistent stopped workspace — the orphan predicate keys on "no owning DB row," not on `stopped` state (RED if the predicate ever regresses to state-based reaping).
  4. A mocked-proxmoxer integration tier exercises real-shaped UPID async-task polling and `ResourceException` error shapes, covering the setup/persistence compute paths the Fake never triggers.
  5. The stop/start e2e cleanup is hardened (07r): per-test workspace-id tracking, an asserted cleanup `DELETE` success, and an explicit two-Start-affordance assertion; the suite is order-independent.

**Plans**: 4 plans
Plans:

- [x] 10-01-PLAN.md — Mocked-proxmoxer integration tier (TEST-01, the hard gate): `mock_proxmox.py` UPID + `ResourceException` factories + self-tests over the real provider
- [x] 10-02-PLAN.md — Stop/start e2e hardening (TEST-02, 07r): W2 asserted cleanup DELETE + W3 two-Start-affordance assertion
- [x] 10-03-PLAN.md — Persistence data-model foundation (WSX-02): `003` migration (`persistent` column + `settings` singleton), DTO field, provider/saga threading, ADR-0011 + ADR-0013
- [x] 10-04-PLAN.md — Reaper carve-out + persistence lock (WSX-04): carve-out comment + negative-control reaper tests + persistent stop->start round-trip

**ADR**: ADR-0013 (persistence model — Tier-1 `persistent` flag; snapshots/suspend deferred); ADR-0011 (setup-state store — the `settings` singleton carrying `setupCompletedAt`, shared with Phase 12)

### Phase 11: Scrollback Restore

**Goal**: A persistent workspace's terminal scrollback survives stop→start — on reconnect the operator sees prior scrollback by reattaching to a worker-side tmux session, with the control-plane relay unchanged.
**Depends on**: Phase 10 (persistence is what makes a stop→start worth restoring scrollback across); parallelizable with Phase 12 — it lives entirely in the separate `cc-worker-config` repo and touches no `api/` or `ui/` code
**Requirements**: WSX-03
**CI-provable**: yes — worker-side, via the hermetic boot harness (stub ttyd records argv); the real tmux reattach across a real stop/start is verified at the Phase 14 homelab smoke (ACC-01)
**Success Criteria** (what must be TRUE):

  1. `burrow-boot.sh` execs ttyd wrapping the worker shell in `tmux new-session -A -s burrow` (idempotent reattach), proven by the boot harness asserting the tmux invocation in the recorded ttyd argv.
  2. `provision-template.sh` bakes tmux (Ubuntu 24.04 apt, pinned) and an `/etc/tmux.conf` setting a bounded history limit and `window-size latest` (the single-reconnecting-web-client resize fix).
  3. A second boot of the same worker reattaches to the existing `burrow` tmux session rather than starting a fresh one (the `-A` idempotency contract), proven hermetically without real Proxmox.
  4. The control-plane terminal relay stays a dumb opaque bridge — no server-side scrollback buffering is added (the explicit anti-pattern stays absent; seam discipline unchanged).

**Plans**: 2 plans
Plans:

- [x] 11-01-PLAN.md: boot-side tmux wrap + reattach harness + ADR-0014 (WSX-03 criteria 1, 3, 4) - tmux new-session -A -s burrow in burrow-boot.sh, argv assertion + second-boot reattach test, ADR-0014.
- [x] 11-02-PLAN.md: worker-template tmux baseline (WSX-03 criterion 2) - add tmux to the apt line + record the 3.4 pin + bake /etc/tmux.conf (history-limit 50000 + window-size latest).

**ADR**: ADR-0014 (tmux scrollback in the worker template — tmux 3.4 over zellij, bounded history, reconnect-survival only)

### Phase 12: Setup Wizard Backend

**Goal**: The control plane exposes a guided-setup API surface — validate a Proxmox host/token read-only, verify the golden template, and reuse the existing health check — behind two new provider-neutral `ComputeProvider` capabilities, with the powerful PVE token kept `.env`-only and never persisted, returned, or logged.
**Depends on**: Phase 10 (the `settings` singleton + `setupCompletedAt` it serves the `setupCompletedAt` flag from); parallelizable with Phase 11
**Requirements**: SETUP-01, SETUP-02, SETUP-03, SETUP-07
**CI-provable**: yes — over the FakeComputeProvider implementing `testConnection`/`verifyTemplate`, plus the Phase 10 mocked-proxmoxer tier for the real-shaped error/permission paths; no real Proxmox
**Success Criteria** (what must be TRUE):

  1. `POST` to a `/api/v1/setup/*` test-connection endpoint validates a provided host + token strictly read-only (capability assertion via the privsep token's `/access/permissions`), reporting connection success and any missing privileges, and creating zero resources (no test-clone, no orphan).
  2. A verify-template endpoint reports whether the golden worker template exists and is usable on the target node, returning a clear pass/fail without mutating anything.
  3. A health/readiness endpoint reuses `/api/v1/health` to confirm the API can reach Proxmox, returning the existing degrade-not-500 shape.
  4. `testConnection` and `verifyTemplate` exist on BOTH the Fake and Proxmox `ComputeProvider` impls with no Proxmox specifics leaking past the ABC (seam-leakage guard stays green).
  5. A sentinel-token test proves the Proxmox token is written only to the gitignored `.env`, validated in-memory, and never persisted to the DB, returned in any `data`/`error` envelope, or written to any log line or event blob.

**Plans**: 2 plans
Plans:

- [x] 12-01-PLAN.md - Compute-seam foundation: testConnection/verifyTemplate ABC + DTOs + Proxmox (ephemeral read-only client, 9-priv assertion) + Fake parity + SecretStr/logger token hardening + read-only getSetupState()
- [x] 12-02-PLAN.md - Setup API surface: POST /api/v1/setup/{test-connection,verify-template} + token-free error codes + SETUP-03 /api/v1/health reuse + the sentinel-token leak hard gate (SETUP-07) + read-only/zero-resource assertion + ADR-0012

**ADR**: ADR-0012 (new `ComputeProvider` capabilities — `testConnection`/`verifyTemplate`, Fake parity); ADR-0011 (setup-state store, if not already landed in Phase 10). *Token-at-rest ADR avoided by design.*

### Phase 13: Setup Wizard UI + First-Run Gate

**Goal**: An unconfigured Burrow presents a guided, re-enterable setup wizard as a first-run gate that walks the operator from token validation through template verification and health to creating their first workspace; once configured the wizard never reappears, and create gains the opt-in persistent toggle.
**Depends on**: Phase 12 (consumes the `/api/v1/setup/*` endpoints + `setupCompletedAt`); for the persistent checkbox half of WSX-02, the Phase 10 `persistent` column
**Requirements**: SETUP-04, SETUP-05, SETUP-06
**CI-provable**: yes — vitest + Playwright over the Fake provider; the real first-workspace-on-real-Proxmox lands at the Phase 14 smoke (ACC-01)
**Success Criteria** (what must be TRUE):

  1. When `settings.setupCompletedAt` is unset, the UI presents `SetupWizard.tsx` as a first-run gate before the workspace list; once set, the wizard does not reappear and the operator lands on the workspace list.
  2. The wizard's final step creates the operator's first workspace and then marks setup complete (`setupCompletedAt` set), transitioning the UI to the normal workspace view.
  3. Re-opening the wizard re-probes current state and lands on the first failing step (idempotent, re-enterable; no persisted checkpoint machine).
  4. `NewWorkspaceModal` exposes a persistent checkbox (default unchecked = ephemeral) that submits the `persistent` flag, completing the UI half of WSX-02 against the Phase 10 backend.

**Plans**: 4 plans
Plans:

- [x] 13-01-PLAN.md — Backend setter + gate endpoints (SETUP-04/05): `DbProvider.setSetupCompleted()` (ABC + SQLite + Postgres stub) + `GET /api/v1/setup/state` + `POST /api/v1/setup/complete` (idempotent), integration-tested over the Fake-backed app
- [x] 13-02-PLAN.md — Setup hooks + persistent checkbox (SETUP-04/05, WSX-02 UI half): `useSetupState`/`useTestConnection`/`useVerifyTemplate`/`useCompleteSetup` hooks + the `persistent` checkbox on `NewWorkspaceModal`
- [x] 13-03-PLAN.md — SetupWizard + first-run gate (SETUP-04/06): `SetupWizard.tsx` (4 auto-advancing steps, re-probe, complete-after-create, hard-gate a11y per 13-UI-SPEC) + the `App.tsx` gate, vitest-proven
- [x] 13-04-PLAN.md — Gate e2e (SETUP-06): Playwright `setup-wizard.spec.ts` — unconfigured shows the gate → walk → complete → gate vanishes; configured skips it, over the Fake

**UI hint**: yes

### Phase 14: First Real-Infra Acceptance

**Goal**: Burrow is proven to actually run on the operator's real Proxmox homelab and to publish a real, verifiable signed release — the human-UAT acceptance gate that flips the long-carried ★ real-infra items (and the per-phase `*-HUMAN-UAT.md` checklists) to passed.
**Depends on**: Phases 10-13 (the wizard, persistence, and scrollback must be real and CI-green before they can be exercised on real hardware); host-prime prerequisites (worker-pool storage, privsep ACL grant) must be operator-confirmed
**Requirements**: ACC-01, ACC-02, ACC-03
**CI-provable**: NO — operator-run human UAT on real Proxmox + a first live GHCR/cosign release; CI never touches real Proxmox by design (this phase is acceptance, not code)
**Success Criteria** (what must be TRUE):

  1. On the dev homelab, a real workspace runs the full create→terminal→stop→start→destroy lifecycle (the H9 gate), and reaper / auto-stop / capacity / real auto node selection behave on real CTs.
  2. A real persistent workspace survives a real stop→start with its disk intact AND its terminal scrollback restored on reconnect (the live proof of WSX-02 + WSX-03 + the reaper carve-out).
  3. The first live release-please PR merges to produce a version bump + changelog + `v*` tag; harden-runner egress is flipped `audit`→`block` with the discovered allowlist; `actionlint` passes.
  4. A real GHCR image publish succeeds and `cosign verify` + `gh attestation verify` pass against the published `@sha256:` digest (verified by digest, not tag).

**Plans**: 2 (14-01 CI hardening: actionlint + harden-runner allowlist-prep; 14-02 acceptance runbook + consolidated HUMAN-UAT). ACC-01/02/03 are operator-run human UAT (verification lands human_needed).

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 0. Contracts, Seams & Golden Template | v1.0 | 7/7 | Complete | 2026-06-10 |
| 1. Control Plane API | v1.0 | 5/5 | Complete | 2026-06-10 |
| 2. Terminal Proxy + React UI | v1.0 | 6/6 | Complete | 2026-06-10 |
| 3. Reproducible Workers | v1.0 | 3/3 | Complete | 2026-06-11 |
| 4. Hardening & Release | v1.0 | 5/5 | Complete | 2026-06-11 |
| 5. Stop/Start Controls + Drawer Polish | v1.1 | 4/4 | Complete | 2026-06-14 |
| 6. CI / Tooling Robustness | v1.1 | 1/1 | Complete | 2026-06-15 |
| 7. Backlog Fixes (Fast-Reconcile + E2E Hardening) | v1.2 | 1/1 | Complete | 2026-06-15 |
| 8. Release Hardening (release-please + harden-runner) | v1.2 | 2/2 | Complete | 2026-06-15 |
| 9. Auto Node Selection | v1.2 | 3/3 | Complete | 2026-06-16 |
| 10. Persistence Data Model + Reaper Carve-out | v1.3 | 4/4 | Complete    | 2026-06-25 |
| 11. Scrollback Restore | v1.3 | 2/2 | Complete    | 2026-06-25 |
| 12. Setup Wizard Backend | v1.3 | 2/2 | Complete    | 2026-06-26 |
| 13. Setup Wizard UI + First-Run Gate | v1.3 | 4/4 | Complete    | 2026-06-26 |
| 14. First Real-Infra Acceptance | v1.3 | 0/? | Not started | - |
