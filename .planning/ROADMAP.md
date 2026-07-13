<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)
- ✅ **v1.1 UI Polish + Stop/Start Controls** — Phases 5-6 (shipped 2026-06-15)
- ✅ **v1.2 Backlog Fixes + Release Automation** — Phases 7-9 (shipped 2026-06-16)
- ✅ **v1.3 Go Live** — Phases 10-14 (shipped 2026-06-26; guided setup wizard + opt-in persistence + scrollback restore + first real-infra acceptance)
- 🚧 **v1.4 Ship & Harden** — Phases 15-22 (in progress; pipeline unblock + green main, ADR-0015 GUI credential store, repo hardening, async-202 create, first signed GHCR release, live homelab acceptance capstone). Cut as v1.4.0.

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

### ✅ v1.3 Go Live (Phases 10-14) — SHIPPED 2026-06-26

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
- [x] **Phase 14: First Real-Infra Acceptance** — operator-run human UAT on real Proxmox + first live GHCR/cosign release (human UAT, not CI) (completed 2026-06-26)

**Anticipated ADRs** (Nygard style, authored within their phase, `docs/adr/`): ADR-0011 setup-state
store (`settings` singleton + `setupCompletedAt`) · ADR-0012 new `ComputeProvider` capabilities
(`testConnection`/`verifyTemplate`, Fake parity) · ADR-0013 persistence model (Tier-1 `persistent`
flag over stop/start; snapshots/suspend explicitly deferred) · ADR-0014 tmux scrollback in the
worker template. *Token-at-rest ADR avoided by design (`.env`-only, validate-in-memory).*

### 🚧 v1.4 Ship & Harden (Phases 15-22) — IN PROGRESS

**Milestone goal:** consolidate and ship everything in flight — unblock the CI/release pipeline,
merge + finish the ADR-0015 GUI-managed credential store (backend done; frontend + onboarding key
remain), harden the repo (Dependabot / CodeQL / backlog), fix the create-UX 504, cut the first real
signed + attested GHCR release, and prove the whole system on the real Proxmox homelab — ending in a
live real-infra acceptance capstone. Cut as **v1.4.0**.

**Shape:** an 8-phase dependency-ordered milestone continuing the numbering from v1.3. Phases 15-21
are CI/config/code (CI-provable over the GitHub-hosted runner + the FakeComputeProvider); Phase 22 is
operator-run human UAT on real Proxmox (acceptance, not code — NOT CI-provable). Grounded in the
2026-07-13 loose-thread recon. Locked-at-definition decisions: cut as v1.4.0 (reconcile
release-please forward from the stale 1.2.0); the credential store is now secret-at-rest by design
(ADR-0015 supersedes the old `.env`-only posture); a 2nd live worker node is confirmed for the
acceptance capstone (ACC-01 item 9 in-scope); multi-agent workers are research-only this milestone
(AGENT-02, no build). Context: ACC-01 items 1-5 (H9 core) already PASSED 2026-07-12 on den01;
`actionlint` (carried ACC-02 item 13) already passed on the live runner (run 29221779815); PR #3
(the credential backend) is mergeable (+18/0 vs main); the true gating work is the three pipeline
blockers (the `oss` ruleset, the mixed-case GHCR owner + syft auth, and the red Trivy `main` gate).

- [ ] **Phase 15: Pipeline Unblock & Green Main** — exclude the release-please branch from the `oss` ruleset, lowercase the GHCR owner + give the SBOM step registry auth so images ship signed+attested, green the Trivy HIGH/CRITICAL gate on main (PC1), reconcile the tag scheme to semver (RELX-03/04/05/06; CI-provable)
- [ ] **Phase 16: Land Credential Backend & Reconcile Release Train** — merge PR #3 onto a green main, reconcile release-please forward from the stale 1.2.0 to v1.4.0, reconcile the secret-at-rest docs to ADR-0015, prune the merged local branch (CRED-01; CI-provable; depends on 15)
- [ ] **Phase 17: Repo Security & Backlog Hygiene** — Dependabot config + automated-security-fixes, CodeQL SAST on the default branch + first-run baseline, clear the 4-item todo backlog (SEC-01/02/03, ROB-01/02; CI-provable; parallelizable)
- [ ] **Phase 18: Credential Store Frontend & Onboarding Key** — wizard admin-secret + credentials steps, admin-gated Settings/Credentials screen, audit read endpoint + panel, `X-Burrow-Admin` client, `BURROW_SECRET_KEY` auto-generation, extended leak test (CRED-02..07; CI-provable; depends on 16)
- [ ] **Phase 19: Create-UX Async-202** — `POST /workspaces` returns 202 + a creating row, the saga runs in a tracked background task, the UI's existing 3s poll drives state; ADR-0017 (UX-01; CI-provable; parallelizable)
- [ ] **Phase 20: Signed GHCR Release & Harden-Runner Block** — cut the clean v1.4.0 tag → green signed+attested release → cosign/attestation verify → flip harden-runner audit→block from the green run's telemetry (ACC-06; CI-provable / CD; depends on 15 + 18)
- [ ] **Phase 21: Multi-Agent Workers Research Spike** — research-only ADR-0018 for Cursor / Copilot CLI / Codex workers, confirm the credential seam is additive; no build (AGENT-02; research-only; parallelizable)
- [ ] **Phase 22: Live Homelab Acceptance Capstone** — operator human UAT on real Proxmox (ACC-01 items 6-11, 2nd live node for item 9) + credential-store live smoke on den01 (ACC-04/05; human UAT, NOT CI-provable; depends on 16 + 18 + 20)

**Anticipated ADRs** (Nygard style, authored within their phase, `docs/adr/`): ADR-0017 async-202
create + background-task lifecycle (Phase 19) · ADR-0018 multi-agent worker design contract
(Phase 21) · ADR-0016 CodeQL/Dependabot security-posture (Phase 17, only if a baseline deviation is
recorded). *ADR-0015 (GUI credential store) already authored; Phase 16 reconciles the docs to it.*

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

### Phase 15: Pipeline Unblock & Green Main

**Goal**: The CI/release pipeline is unblocked end-to-end — release-please can maintain its release branch and merge to a `vX.Y.Z` tag, every GHCR reference builds from a lowercased owner with SBOM registry auth so published images ship signed + attested (not the current unsigned partial-publish), `main` passes the Trivy HIGH/CRITICAL gate (PC1), and the tag scheme is reconciled to semver owned by release-please. This is the true gating work: everything else in v1.4 lands on top of a green main.
**Depends on**: Nothing new (builds on the v1.2 release-please + `release.yml` supply-chain path shipped Phase 8, and the Phase 14 harden-runner/actionlint prep)
**Requirements**: RELX-03, RELX-04, RELX-05, RELX-06
**CI-provable**: yes — GitHub ruleset config + `release.yml`/`ci.yml` changes proven by a green push:main run and a cleanly-maintained release PR; no real Proxmox
**Success Criteria** (what must be TRUE):

  1. The active `oss` ruleset no longer rejects the release-please bot's ref update — `refs/heads/release-please--**` is excluded (or the Actions bot is a bypass actor) — so the release PR maintains cleanly and its branch updates without a push rejection (RELX-03).
  2. `release.yml` builds every GHCR reference from a lowercased owner and the syft SBOM step authenticates to the registry, so on a tagged run SBOM + cosign keyless sign + SLSA attestation all succeed and images publish signed + attested (RELX-04).
  3. CI on `main` passes the Trivy HIGH/CRITICAL gate (PC1 green) via patched base-image digests and/or a reviewed ignore policy (owner + expiry) for unfixable base CVEs (RELX-05).
  4. Release tags are semver `vX.Y.Z` owned by release-please, a hand-pushed milestone tag no longer triggers `release.yml`, and the stale `1.2.0` release PR is unblocked to advance (its actual forward-reconciliation to v1.4.0 lands with the CRED-01 feat merge in Phase 16) (RELX-06).

**Plans**: 3 plans (all Wave 1, parallelizable; disjoint files)
Plans:

- [x] 15-01-PLAN.md — release.yml: lowercase GHCR owner into one reused base + syft registry auth + narrow tag trigger to semver (RELX-04, RELX-06)
- [ ] 15-02-PLAN.md — Trivy green-main gate: ci.yml ignore-unfixed + reviewed .trivyignore + repin base image digests (RELX-05)
- [ ] 15-03-PLAN.md — oss ruleset exclusion for the release-please branch: operator-run gh api runbook + apply (RELX-03; autonomous: false)

### Phase 16: Land Credential Backend & Reconcile Release Train

**Goal**: The ADR-0015 credential-store backend (PR #3, +18/0, mergeable) lands on a green `main`, release-please is reconciled forward from the stale 1.2.0 to target v1.4.0, the secret-at-rest docs are reconciled to reference ADR-0015 (no longer asserting "no secret-at-rest"), and the merged local branch is pruned.
**Depends on**: Phase 15 (PR #3 must merge onto a GREEN main — the Trivy gate + signed-release path must be green first, or the merge lands on a red pipeline)
**Requirements**: CRED-01
**CI-provable**: yes — the merge + a green post-merge `main` run + a release PR advancing to v1.4.0; the docs reconciliation is a repo change
**Success Criteria** (what must be TRUE):

  1. PR #3 (the ADR-0015 credential-store backend, migration `004`) is merged to `main` and the post-merge `main` CI run is green (build + tiered tests + scans all pass on the merge commit).
  2. release-please is reconciled forward from the stale 1.2.0: the open release PR proposes v1.4.0 (the credential feat drives the minor), and hand-pushed tags stay inert (the Phase 15 semver ownership holds through the merge).
  3. The secret-at-rest docs (ROADMAP / STATE / tech-spec) are reconciled to reference ADR-0015 — the prior "validate-in-memory, `.env`-only, no secret-at-rest" assertions are corrected to the Fernet-encrypted-at-rest posture.
  4. The merged local credential-store branch (`feat/gui-managed-secrets`) is pruned — no stale branch lingering after the squash-merge.

**Plans**: TBD

### Phase 17: Repo Security & Backlog Hygiene

**Goal**: The repo's security posture is completed and the accumulated backlog is cleared — Dependabot version-updates + automated-security-fixes are live, CodeQL SAST runs on the default branch for Python + JS/TS with its first findings triaged/baselined (today code scanning is 100% Trivy image CVEs, zero source SAST), and the four carried backlog nits are closed.
**Depends on**: Nothing new (repo-config + small code/test changes; parallelizable off Phase 15/16 — it touches `.github/` + a boot-test + a service predicate, disjoint from the credential/release surface)
**Requirements**: SEC-01, SEC-02, SEC-03, ROB-01, ROB-02
**CI-provable**: yes — Dependabot/CodeQL config proven by their first live runs on the default branch; the ROB fixes land regression tests over the Fake / boot harness
**Success Criteria** (what must be TRUE):

  1. `.github/dependabot.yml` configures weekly, grouped version-updates for `pip`/`uv` (`api/`), `npm` (`ui/`), and `github-actions` (`.github/workflows/`), and Dependabot opens its first grouped update PRs (SEC-01).
  2. Dependabot automated-security-fixes are enabled so a vulnerable dependency yields an auto-remediation PR (SEC-02).
  3. CodeQL SAST runs on the default branch for Python + JavaScript/TypeScript (source SAST, not only Trivy image CVEs), and its first-run findings are triaged/baselined — recorded, dismissed-with-reason, or fixed (SEC-03).
  4. The `_is_running_or_locked` bare `"lock"` substring match (WR-04) is removed in favor of the precise `"is locked"`, guarded by a failing-first regression test; the already-resolved 07r and WR-02 todos are filed/closed (ROB-01).
  5. The tautological `worker.env` leak assertion in `test_burrow_boot.py` is replaced with an assertion over files the boot script actually writes (or removed, pointing at the stdout/stderr scrub), and em-dashes in worker-template shell comments are swept (ROB-02).

**Plans**: TBD

### Phase 18: Credential Store Frontend & Onboarding Key

**Goal**: The ADR-0015 credential store gains its full operator-facing surface — the milestone's ship blocker (the backend is done but curl-only). Admin-secret + credentials wizard steps, an admin-gated Settings/Credentials screen with status + rotation, an audit read endpoint + panel, the `X-Burrow-Admin` client header, `BURROW_SECRET_KEY` auto-generation in onboarding, and an extended sentinel leak test — turning the curl-only backend into a novice-usable GUI.
**Depends on**: Phase 16 (the credential backend + migration `004` must be merged to `main` before the frontend can bind to `/setup/admin-secret`, `/setup/credentials`, `/setup/audit`)
**Requirements**: CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CRED-07
**CI-provable**: yes — vitest + Playwright over the Fake + the real-temp-SQLite integration tier; the live den01 apply is the Phase 22 ACC-05 smoke
**Success Criteria** (what must be TRUE):

  1. The operator can set a local admin secret in the setup wizard (`POST /setup/admin-secret`) and the credential surface is admin-gated via an `X-Burrow-Admin` header sent by the client (CRED-02).
  2. The operator can enter the Proxmox token + GitHub PAT in the wizard and have them stored encrypted at rest (Fernet) — replacing the v1.3 "validated in memory only, never stored" step (CRED-03).
  3. An admin-gated post-setup Credentials/Settings screen shows credential status (set + last4 + updatedAt) and supports rotation, and never returns a secret value (CRED-04).
  4. An admin-gated read-only audit view (`GET /setup/audit` + a GUI panel) surfaces the append-only credential audit trail (CRED-05).
  5. `BURROW_SECRET_KEY` is auto-generated into `.env` on first run when empty (novice-safe) with documented key-loss recovery, a missing/undecryptable key never crashes worker boot (CRED-06), and an extended sentinel-through-`/setup/credentials` leak test proves plaintext appears in no DB cell, API envelope, or log line — only Fernet ciphertext + a 4-char last4 persist (CRED-07).

**Plans**: TBD
**UI hint**: yes

### Phase 19: Create-UX Async-202

**Goal**: Creating a workspace returns immediately (`202` + a `creating` row) with the boot saga running in a tracked background task, so a slow real boot never `504`s — the UI's existing 3s list poll drives `creating`→`running`/`error` and the setup-wizard create step no longer blocks. Cures the ~60s create 504.
**Depends on**: Nothing new for the mechanism (builds on the v1.0 create saga + state machine + the existing 3s poll); parallelizable off Phase 15/16 — it touches the create-saga lifecycle + a small UI wait-state, disjoint from the credential/release surface (it composes cleanly with the Phase 13 wizard create step + the Phase 18 wizard credentials step)
**Requirements**: UX-01
**CI-provable**: yes — over the Fake with an injected slow boot; the real >60s boot no-504 is confirmed at the Phase 22 ACC-04 smoke
**Success Criteria** (what must be TRUE):

  1. `POST /workspaces` returns `202` with the `creating` row immediately and never blocks on the boot saga — an injected slow boot returns 202 well under the prior ~60s 504 threshold.
  2. The boot saga runs in a tracked background task with a defined lifecycle (started / awaited / cancelled-on-shutdown), and a saga failure transitions the row to `error` (not a hung `creating`).
  3. The UI's existing 3s list poll drives `creating`→`running`/`error` with a visible creating affordance, and the setup-wizard create step no longer blocks on a synchronous create.
  4. ADR-0017 records the async-202 create + background-task lifecycle contract (task tracking, shutdown-drain, failure→error mapping).

**Plans**: TBD

### Phase 20: Signed GHCR Release & Harden-Runner Block

**Goal**: The first clean `v1.4.0` tag drives a green, signed + attested `release.yml` run to GHCR, `cosign verify` + `gh attestation verify` pass against the published `@sha256:` digest (completing carried ACC-03), and harden-runner egress is flipped `audit`→`block` from the green run's discovered allowlist (completing carried ACC-02 item 14).
**Depends on**: Phase 15 (a green signed-release path + green main) + Phase 18 (v1.4.0 must contain the full credential-store GUI — the milestone's ship blocker — before the tag is cut)
**Requirements**: ACC-06
**CI-provable**: yes / CD — the tagged release runs on the GitHub-hosted runner (a green signed+attested publish + on-runner cosign/attestation verify + the egress block-flip from the run's telemetry); the live re-verify against a homelab-pulled image rides along at Phase 22
**Success Criteria** (what must be TRUE):

  1. A clean `v1.4.0` tag (owned by release-please) drives a green `release.yml` run that publishes signed + attested images to GHCR (SBOM + cosign keyless + SLSA attestation all succeed).
  2. `cosign verify` + `gh attestation verify` pass against the published `@sha256:` digest (verified by digest, not tag) — completing carried ACC-03.
  3. harden-runner egress is flipped `audit`→`block` using the allowlist discovered from the green run's telemetry (Fulcio/Rekor/TUF/OIDC/GHCR pre-seeded), and a subsequent run stays green under the block policy — completing carried ACC-02 item 14. (actionlint, carried ACC-02 item 13, already passed on the live runner — run 29221779815.)

**Plans**: TBD

### Phase 21: Multi-Agent Workers Research Spike

**Goal**: A research-only ADR / design contract for running Cursor / Copilot CLI / Codex CLI in workers is produced (no build), confirming the v1.4 credential seam is additive for future per-agent auth.
**Depends on**: Nothing new (research-only; reads the ADR-0015 credential seam landed in Phase 16); parallelizable off the earlier work
**Requirements**: AGENT-02
**CI-provable**: n/a — a research ADR / design doc, no code; the deliverable is the reviewed ADR-0018 + a written seam-additivity confirmation, not a green run or real-infra UAT
**Success Criteria** (what must be TRUE):

  1. ADR-0018 (Nygard style, `docs/adr/`) documents a design contract for running Cursor / Copilot CLI / Codex CLI in workers — agent registry shape, per-agent secrets seam, create-modal picker — explicitly no build this milestone.
  2. The ADR confirms the v1.4 ADR-0015 credential seam is additive for future per-agent auth: the store extends without a rewrite, the `DbProvider` / secret-key seams stay abstract, and the exact extension points are cited.
  3. The scope boundary is recorded: AGENT-03+ (actually booting the agents — agent registry + per-agent secrets + `WorkspaceCreate` DTO + create-modal picker) is a full milestone of its own, deferred out of v1.4.

**Plans**: TBD

### Phase 22: Live Homelab Acceptance Capstone

**Goal**: The milestone is proven on the real Proxmox homelab — the remaining ACC-01 lifecycle items (6-11) pass on real CTs across ≥2 live nodes, and the GUI credential store is verified live on den01 (migration `004` applies, a GUI-set token applies without a restart and survives one). The human-UAT capstone that closes v1.4.
**Depends on**: Phase 16 (credential backend live) + Phase 18 (credential GUI) + Phase 20 (the signed v1.4.0 release to verify + deploy). ACC-01 items 1-5 (the H9 core) already PASSED 2026-07-12 on den01.
**Requirements**: ACC-04, ACC-05
**CI-provable**: NO — operator-run human UAT on real Proxmox + a live credential-store smoke on den01; CI never touches real Proxmox by design (this phase is acceptance, not code)
**Success Criteria** (what must be TRUE):

  1. On the homelab, the remaining real-infra lifecycle passes (carried v1.3 ACC-01 items 6-11): the reaper destroys a real injected orphan LXC + frees its VMID on a non-default node; idle auto-stop fires after the real `idle_window_s` (a brief reconnect does not trip it); capacity holds under real concurrent creates (ACC-04).
  2. Real least-loaded node selection lands correctly across ≥2 live nodes — item 9, the confirmed 2nd live worker node exercised (ACC-04).
  3. A persistent workspace survives a real stop→start with its disk + scrollback intact, and the reaper never destroys a persistent stopped workspace (ACC-04).
  4. The GUI credential store is verified live on den01: migration `004` applies on the real SQLite, a GUI-set Proxmox token applies without a restart and survives a restart (ACC-05).
  5. (Rides along) ACC-06's signed v1.4.0 release re-verifies live: `cosign verify` + `gh attestation verify` pass against a homelab-pulled `@sha256:` image (ACC-06 is proven on the runner in Phase 20; this is the live re-verify against a pulled image).

**Plans**: TBD

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
| 14. First Real-Infra Acceptance | v1.3 | 2/2 | Complete   | 2026-06-26 |
| 15. Pipeline Unblock & Green Main | v1.4 | 1/3 | In Progress|  |
| 16. Land Credential Backend & Reconcile Release Train | v1.4 | 0/TBD | Not started | - |
| 17. Repo Security & Backlog Hygiene | v1.4 | 0/TBD | Not started | - |
| 18. Credential Store Frontend & Onboarding Key | v1.4 | 0/TBD | Not started | - |
| 19. Create-UX Async-202 | v1.4 | 0/TBD | Not started | - |
| 20. Signed GHCR Release & Harden-Runner Block | v1.4 | 0/TBD | Not started | - |
| 21. Multi-Agent Workers Research Spike | v1.4 | 0/TBD | Not started | - |
| 22. Live Homelab Acceptance Capstone | v1.4 | 0/TBD | Not started | - |
