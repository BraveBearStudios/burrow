<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Requirements: Burrow — Milestone v1.3 "Go Live"

**Defined:** 2026-06-24
**Core Value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.

> v1.3 takes Burrow from CI-proven-over-Fake to actually running on the operator's real
> Proxmox homelab: a guided in-app setup wizard, opt-in workspace persistence + scrollback
> restore, and the first real-infra acceptance run. Grounded in `.planning/research/SUMMARY.md`.
> Decisions locked at definition: persistence is **opt-in per workspace** (default ephemeral);
> the reaper gets a **carve-out + regression test only** (no new auto-reaping); the Proxmox
> token is **validate-in-memory, `.env`-only** (no secret-at-rest). Multi-agent workers are
> **deferred to v1.4** (research-first).

## Milestone v1.3 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase (see Traceability).
Wizard, persistence, scrollback, and test-hardening are CI-provable over the FakeComputeProvider;
the ACC items are operator-run human UAT on real infrastructure.

### Setup Wizard (SETUP)

- [x] **SETUP-01**: Operator can enter a Proxmox host + API token in the setup wizard and have it validated **read-only** (capability assertion via the privsep token's `/access/permissions`), reporting connection success and any missing privileges without creating any resource.
- [x] **SETUP-02**: The wizard verifies the golden worker template exists and is usable on the target node before setup can complete.
- [x] **SETUP-03**: The wizard runs a control-plane health/readiness check (reusing `/api/v1/health`) confirming the API can reach Proxmox.
- [x] **SETUP-04**: As its final step, the wizard creates the operator's first workspace.
- [x] **SETUP-05**: When Burrow is unconfigured (`settings.setupCompletedAt` unset) the UI presents the wizard as a first-run gate before the workspace list; once configured the wizard does not reappear.
- [x] **SETUP-06**: Wizard steps are idempotent and re-enterable — re-opening re-probes current state and lands on the first failing step (no persisted checkpoint machine).
- [x] **SETUP-07**: The operator's Proxmox token is written only to the gitignored `.env`, validated in-memory, and is never persisted to the database, returned in an API response, or written to logs.

### Workspace Persistence (WSX)

- [x] **WSX-02**: Operator can mark a workspace **persistent** at create time (default remains ephemeral); a persistent workspace survives stop→start with its disk and database row intact instead of being destroyed.
- [x] **WSX-03**: A persistent workspace's terminal **scrollback survives stop→start** — on reconnect the operator sees prior scrollback (worker-side tmux `new-session -A` reattach).
- [x] **WSX-04**: The orphan reaper **never destroys a persistent stopped workspace** (the orphan predicate keys on "no owning row," not on "stopped" state), proven by a negative-control regression test.

### Test Hardening (TEST)

- [x] **TEST-01**: New setup/persistence compute paths are covered by a **mocked-proxmoxer integration tier** exercising real-shaped UPID async-task polling and `ResourceException` error shapes (closing the Fake-vs-real gap before the persistence-compute work).
- [x] **TEST-02**: The stop/start e2e suite cleanup is hardened (07r) — per-test workspace-id tracking (W1), asserted cleanup `DELETE` success (W2), and an explicit two-Start-affordance assertion (W3).

### Real-Infra Acceptance (ACC) — operator-run human UAT on real hardware

- [ ] **ACC-01**: On the dev homelab, real create→terminal→stop→start→destroy passes (the H9 gate), along with reaper / auto-stop / capacity on real CTs, real auto node selection, and **real persistent stop/start + scrollback restore**.
- [ ] **ACC-02**: The first live release-please PR merges to produce a version bump + changelog + `v*` tag; harden-runner egress is flipped `audit`→`block` with the discovered allowlist; `actionlint` passes.
- [ ] **ACC-03**: A real GHCR image publish succeeds and `cosign verify` + `gh attestation verify` pass against the published `@sha256:` digest.

## Future Requirements

Deferred. Tracked, not in this milestone's roadmap.

### Persistence v2 (WSX)

- **WSX-05**: Point-in-time snapshot + rollback of a workspace. *Needs `zfspool`/`lvmthin`/`ceph` storage + the `VM.Snapshot` privilege + a sprawl bound. Deferred from v1.3 (Tier-1 stop/start chosen).*
- **WSX-06**: Suspend/resume (Tier-2 — live process state preserved across stop). *Blocked: CRIU suspend is unsupported/broken for unprivileged LXC.*
- **WSX-07**: Cross-reboot scrollback (disk-logged history via `tmux pipe-pane`), beyond reconnect-survival.

### Multi-Agent Workers (AGENT)

- **AGENT-01+**: Boot Cursor / GitHub Copilot CLI / Codex CLI in workers (not only Claude Code). *A full milestone of its own — agent registry + per-agent secrets seam + `WorkspaceCreate` DTO + create-modal picker; research-first (headless ttyd support, non-interactive auth, license terms). Deferred to v1.4; todo stays in `.planning/todos/pending/`.*

## Out of Scope

Explicitly excluded. Anti-features from research belong here with reasoning.

| Feature | Reason |
|---------|--------|
| Browser-side Proxmox token/role/template **creation** | Security footgun; contradicts least-priv. The wizard validates an operator-provided token + guides the manual PVE-side privsep steps; it never self-provisions a privileged identity. |
| Token persisted at rest (DB / secret store) | v1.3 keeps the `.env`-only, validate-in-memory posture (token UX decision A); no new secret-at-rest surface, no encryption-at-rest decision this milestone. |
| Keeping live processes alive across stop (CRIU suspend) | Unsupported for unprivileged LXC; Tier-1 `pct stop`/`start` restarts the process (disk survives). |
| Snapshots / rollback | Drags in the storage-backend + `VM.Snapshot` privilege + sprawl classes; deferred to WSX-05. |
| Infinite-retention scrollback | Bounded last-N only; unbounded history is CPU/disk-costly. |
| Auto-rerunning a resurrected command on reattach | Reattach to the live tmux session only; no command replay. |
| Control-plane-side session/terminal recording | The relay stays a dumb opaque bridge; no server-side buffering (explicit anti-pattern). |
| Auto-reap of stopped **ephemeral** workspaces | Carve-out-only chosen; no new reaper code/TTL this milestone. |
| Multi-agent workers (Cursor / Copilot / Codex) | Full milestone of its own; research-first; deferred to v1.4. |
| Real-Proxmox exercise in CI | CI proves contracts over the FakeComputeProvider + mocked proxmoxer; real-infra validation is the ACC human UAT (ci-cd §4.4). |

## Traceability

Finalized by the roadmapper (2026-06-25). Each requirement maps to exactly one phase; no requirement appears in two phases. Phases 10/12/13 are CI-provable over the FakeComputeProvider, Phase 11 is worker-side (CI-provable via the boot harness), Phase 14 is operator-run human UAT on real infra.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WSX-02  | Phase 10 | Complete |
| WSX-04  | Phase 10 | Complete |
| TEST-01 | Phase 10 | Complete |
| TEST-02 | Phase 10 | Complete |
| WSX-03  | Phase 11 | Complete |
| SETUP-01 | Phase 12 | Complete |
| SETUP-02 | Phase 12 | Complete |
| SETUP-03 | Phase 12 | Complete |
| SETUP-07 | Phase 12 | Complete |
| SETUP-04 | Phase 13 | Complete |
| SETUP-05 | Phase 13 | Complete |
| SETUP-06 | Phase 13 | Complete |
| ACC-01  | Phase 14 | Pending |
| ACC-02  | Phase 14 | Pending |
| ACC-03  | Phase 14 | Pending |

**Coverage:**

- v1.3 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

**ADRs anticipated** (authored within their phase, `docs/adr/`): ADR-0011 setup-state store · ADR-0012 new `ComputeProvider` capabilities (`testConnection`/`verifyTemplate`) · ADR-0013 persistence model (Tier-1 `persistent` flag) · ADR-0014 tmux scrollback. *Token-at-rest ADR avoided by design.*

---
*Requirements defined: 2026-06-24*
*Last updated: 2026-06-25 — traceability finalized by the roadmapper against ROADMAP.md Phases 10-14 (15/15 mapped, 0 unmapped, no duplicates)*
