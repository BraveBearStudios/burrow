<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project Research Summary — Milestone v1.3 "Go Live"

**Project:** Burrow
**Milestone:** v1.3 Go Live (Guided Homelab Setup + Real-Infra Acceptance + Persistence)
**Researched:** 2026-06-24
**Confidence:** HIGH

> **How to read this file.** v1.3 is *not* greenfield. It is mostly **composition + verification over the complete, shipped v1.2 substrate**: the setup wizard recomposes already-shipped surfaces with zero new dependencies; persistence is already true at the compute layer (`stopCt` preserves the disk), so WSX-02 is a `persistent` flag + a reaper carve-out test + honest UI; scrollback adds a terminal multiplexer to the worker. Multi-agent workers (Cursor/Copilot/Codex) are **OUT** — deferred to v1.4, research-first. The decisive technical choices are **tmux 3.4** (over zellij) and **Tier-1 plain `pct stop`/`start`** (over CRIU suspend and over snapshots). For the v1.0-era substrate research, see the git history of `STACK.md`/`FEATURES.md`/`ARCHITECTURE.md` and the preserved `PITFALLS.md` (15 still-valid substrate pitfalls); the v1.3 delta is `PITFALLS-v1.3.md`.

## Executive Summary

Burrow already does the hard parts: clone an ephemeral Proxmox LXC per workspace, boot Claude Code + ttyd inside it, bridge the terminal to a tiling browser UI, reconcile/ reap/auto-stop, and ship a signed/attested container. v1.3 makes that real on the operator's homelab and rounds three soft edges:

1. **In-app setup wizard** — a guided first-run flow (validate a Proxmox host/token, verify the golden template, health-check, land the first workspace) that recomposes the shipped `/api/v1/health` signal + the `NewWorkspaceModal` saga-checklist UX. **Zero new deps**, CI-provable over the Fake provider behind two new `ComputeProvider` methods.
2. **Real-boot v2 persistence** — workspaces that survive stop/start instead of being destroyed (**WSX-02 = a `persistent` flag over the existing `stopped` state + `stopCt`/`startCt`; no compute rewrite**), and terminal scrollback that survives a reconnect (**WSX-03 = wrap ttyd in `tmux new-session -A` in the worker**).
3. **First real-infra acceptance (ACC-01/02/03)** — operator-run human UAT on real Proxmox + the first live GHCR/cosign release. Validation, not new code.

The whole milestone is small in code and large in verification. The risk is concentrated in two places: the **reaper-destroys-a-persistent-workspace hazard** (a state-machine carve-out + a negative-control regression test), and the **structural gap between the FakeComputeProvider and real proxmoxer** (a mocked-proxmoxer integration tier that returns real-shaped UPID async tasks + `ResourceException` error shapes, landed before the persistence-compute work).

## Reconciled Decisions (the cross-researcher conflicts, resolved)

| # | Question | Resolution | Winning evidence |
|---|----------|-----------|------------------|
| R-1 | Is worker ttyd currently `--once`? | **No — ttyd is already persistent** (`exec claude`, no `--once`). L1 scrollback (reattach to the live PTY on reconnect) ALREADY works. v1.3's real work is **L2: scrollback surviving stop/start**. | FEATURES agent read `burrow-boot.sh` directly; the `--once` claim was a stale v1.0 PROJECT.md open-question (B2) since resolved. |
| R-2 | WSX-02 approach: snapshot? suspend? | **Tier 1 = resume-only: plain `pct stop`/`start`** (disk survives, process restarts; reuse the existing `stopped` state; add a `persistent` flag column). **Snapshots/rollback and CRIU suspend are OUT for v1.3.** | CRIU suspend is broken on unprivileged LXC; snapshots drag in zfspool/lvmthin storage + `VM.Snapshot` privilege + sprawl. Pitfalls + Architecture + Features all converge. |
| R-3 | Is the reaper a hazard to persistent workspaces? | **Verify the predicate keys on "no owning row," NOT on "stopped" state, AND land a negative-control regression test** proving a persistent stopped workspace is never reaped. Hard phase gate. | PITFALLS ranks it #1 risk; ARCHITECTURE believes it is already row-based-safe. Either way: verify + lock with a test. |
| R-4 | Build order? | Persistence data model (foundation) → worker-side tmux scrollback (parallelizable, separate `cc-worker-config` repo) → wizard backend → wizard UI → real-infra acceptance (last). Phases 10-14. | ARCHITECTURE + Pitfalls + Features agree on the dependency chain. |
| R-5 | How to close the CI-vs-real gap? | Add a **mocked-proxmoxer integration tier** (real-shaped UPID polling + `ResourceException`) before the persistence-compute work. | The Fake is engineered to never trigger error/UPID paths — they are the least-exercised code in the app. |
| R-6 | Are ACC-01/02/03 code REQ-IDs? | **No — they are operator-run human-UAT acceptance criteria.** The wizard + persistence + scrollback ARE CI-provable over the Fake. | All four researchers; matches PROJECT.md "Real-Proxmox in CI = out of scope." |

## Key Findings

### Stack (delta only — confidence HIGH)

- **Terminal multiplexer = tmux 3.4 (Ubuntu 24.04 apt), NOT zellij.** Decisive: tmux is in the worker distro repo (reproducible, apt-pinnable, no curl-pipe binary), ttyd's own wiki documents the exact `ttyd tmux new -A -s burrow` pattern, and tmux 3.4 has `window-size latest` (the single-reconnecting-web-client resize fix). zellij is pre-1.0 with no 24.04 apt package. **Integration point:** one `exec ttyd` line in `cc-worker-config/lxc/worker-template/burrow-boot.sh` + a baked `/etc/tmux.conf` in `provision-template.sh`. **Zero `api/` or `ui/` changes** — the WS proxy and xterm.js are agnostic to what runs behind ttyd.
- **Setup wizard = zero new deps, frontend or backend.** Plain TanStack Query mutations + a Zustand step slice → a new `api/routers/setup.py` over existing `healthcheck`/`getStatus`/`getNodeMemory` + two new `ComputeProvider` methods. The Proxmox token reuses `settings.proxmox_token_value` (`.env`-only), validate-in-memory, never persisted to DB, never returned/logged.
- **Release chain: keep the existing pins.** `cosign-installer@v3.10.0` (installs cosign v2.x; do NOT chase cosign v3 → needs installer v4); syft via `sbom-action@v0.20.7`; Trivy's SHA-pin is the correct mitigation for 2026's Trivy compromises; `release-please-action@v4.4.1` opens the v1.3.0 PR on first `push:main`.

### Features (table-stakes / differentiator / anti-feature)

- **Setup wizard** — *table stakes:* test-connection, validate-permissions (read-only capability assert), verify-template, health, success + first-workspace; first-run gate ("Burrow not configured yet"). *Differentiator:* re-enterable steps that land on the first failing probe (resumability = re-probe on open; **no DB checkpoint machine — YAGNI**).
- **Persistence** — *table stakes:* a `persistent` workspace survives stop/start (disk + state row intact) and honestly tells the operator scrollback is reconnect-restored. *Differentiator:* none needed for v1.3.
- **Scrollback** — *table stakes (already met):* L1 reattach to the live PTY on reconnect. *Real v1.3 work:* L2 — scrollback survives stop/start via the multiplexer's in-memory buffer on the persisted disk.
- **Anti-features — explicitly excluded to stop creep:** browser-side Proxmox token/template *creation* (security footgun, contradicts least-priv); keeping live processes alive across stop (CRIU territory); infinite-retention scrollback; auto-rerunning the resurrected command; control-plane-side session recording; snapshots/rollback (deferred v1.4+).

### Architecture (integration points — confidence HIGH, source-grounded)

- **Wizard:** 5 new `/api/v1/setup/*` endpoints → a new `SetupService`; the health step REUSES `/api/v1/health`. "Configured?" lives in a **new singleton `settings` table** (`003` migration) with an explicit `setupCompletedAt` (not a derived heuristic). Stays CI-provable behind **two new `ComputeProvider` methods — `testConnection`, `verifyTemplate` — implemented in BOTH Fake and Proxmox.** Token stays `.env`-only (validate in-memory, never persist) — preserves the ADR-0002 secret-hygiene posture (no token-at-rest ADR needed).
- **Persistence:** add a `persistent` column (`003` migration) chosen at create time; reuse the existing `stopped` state + `stopCt`/`startCt` (no `ComputeProvider` ABC change for Tier 1). Reconciler/auto-stop must treat a `persistent` stopped workspace as durable.
- **Scrollback:** wrap ttyd's command in `tmux new-session -A -s burrow` (idempotent reattach). The control-plane relay (`terminal.py`) stays a **dumb opaque bridge** — server-side buffering is an explicit anti-pattern.
- **Data model:** one `003` migration carries both the `settings` singleton and the `persistent` column.

### Watch Out For (top pitfalls → prevention → owning phase)

1. **Reaper destroys a persistent stopped workspace (#1 risk).** → Verify the orphan predicate keys on "no owning row," not "stopped"; land a negative-control regression test. → **Phase 10 (hard gate).**
2. **Fake-vs-real proxmoxer gap is structural.** Error-handling + UPID-polling are the least-exercised paths. → Mocked-proxmoxer integration tier (real-shaped UPIDs + `ResourceException`). → **Phase 10, before any compute change.**
3. **Wizard is a new ingress for the powerful PVE token.** → Write-only, redacted at the logging boundary, gitignore-guarded, never round-tripped through `data`/`error`; validation read-only + capability-asserting (privsep `--token` `/access/permissions` read), no orphan-creating test-clones. → **Phase 12/13.**
4. **CRIU suspend / snapshot storage traps.** → Why v1.3 is Tier-1 stop/start only; snapshots need zfspool/lvmthin + `VM.Snapshot` privilege + a sprawl bound (deferred). → **Phase 10 decision, flagged as host-prime prereq.**
5. **First cosign/GHCR release traps.** → Verify by `@sha256:` digest not tag; exactly 4 publish perms (packages:write, id-token:write, attestations:write, contents:read) or an opaque OIDC failure; `gh attestation verify` can exit-0-on-failure (assert on output); harden-runner block-flip must be audit-derived + pre-seed Fulcio/Rekor/TUF; the `GITHUB_TOKEN` tag-retrigger can silently skip publish. → **Phase 14 (runbook).**

## Implications for Roadmap

**Suggested phases: 5 (Phases 10-14).** Phase numbering continues from v1.2's last phase (9).

- **Phase 10 — Persistence data model + reaper carve-out** *(CI-provable over Fake).* `003` migration (`settings` singleton + `persistent` column); verify + lock the reaper predicate with a negative-control test; land the mocked-proxmoxer integration tier. Foundation — lands first.
- **Phase 11 — Scrollback restore (WSX-03 L2, worker-side)** *(separate `cc-worker-config` repo; parallelizable with 12).* tmux in `burrow-boot.sh` + `/etc/tmux.conf` in `provision-template.sh`; bounded history; idempotent reattach.
- **Phase 12 — Setup wizard backend** *(CI-provable over Fake).* `testConnection`/`verifyTemplate` on both providers; `routers/setup.py` + `SetupService`; token hygiene + provider-neutral DTOs.
- **Phase 13 — Setup wizard UI + first-run gate** *(CI-provable over Fake).* `SetupWizard.tsx`, the `App.tsx` first-run gate off `setupCompletedAt`, the `persistent` checkbox in `NewWorkspaceModal`.
- **Phase 14 — First real-infra acceptance (ACC-01/02/03)** *(human UAT — operator-run on real Proxmox + first live GHCR/cosign release).* Build last; gated on the wizard + persistence being real.

**Build-order rationale:** persistence data model is the shared foundation (the `persistent` flag + reaper carve-out gate everything persistence-touching); scrollback is worker-side and parallelizes; wizard UI consumes wizard-backend endpoints; acceptance verifies the lot on real infra.

### ADRs (Nygard style, `docs/adr/`)

- **ADR-0011** — setup-state store (`settings` singleton + `setupCompletedAt`).
- **ADR-0012** — new `ComputeProvider` capabilities (`testConnection`, `verifyTemplate`), Fake parity.
- **ADR-0013** — persistence model (Tier 1 `persistent` flag over stop/start; snapshots/suspend explicitly deferred).
- **ADR-0014** — tmux scrollback in the worker template.
- *Token-at-rest ADR avoided by design* (`.env`-only, validate-in-memory).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack delta | HIGH | tmux-vs-zellij verified (ttyd wiki + apt availability + zellij-not-packaged); wizard no-new-deps confirmed against live `package.json`/`config.py`; release pins verified upstream incl. the cosign-installer v3-vs-v4 gotcha. |
| Features scope | HIGH | Anchored to the actual `/health` endpoint + `NewWorkspaceModal` code + the shipped state machine; anti-features explicit. |
| Architecture | HIGH | Grounded in read `api/` source + ADR-0001..0010 + `burrow-boot.sh`; integration points named in real files. |
| Pitfalls | HIGH | reaper hazard, Fake-vs-real gap, token hygiene, CRIU/snapshot limits, first-cosign/GHCR traps all source-verified. |

**Overall confidence:** HIGH

### Gaps to Address (open questions for roadmapper / operator)

- **WSX-02 rollback vs resume:** resolved to resume-only for v1.3 (recommendation accepted). Snapshots → v1.4+.
- **"Reap stale stopped ephemerals" rule:** a product decision — the only thing that would turn `persistent` into reaper *code* (vs just a regression test). Decide in Phase 10.
- **Wizard token UX:** Option A (validate-then-restart, recommended, no posture change) vs Option B (persist token → ADR + scope risk). Lean A.
- **Cross-reboot scrollback** (disk-logged history via `tmux pipe-pane`) is OUT unless trivially free — L2 reconnect-survival is the v1.3 bar.
- **Real-infra-only unknowns** (exact proxmoxer snapshot/param names, the operator's worker-pool storage type, privsep ACL depth, cosign keyless identity, harden-runner allowlist) — confirmed at the Phase 14 homelab smoke + first-release telemetry; host-prime prerequisites (ZFS/LVM-thin storage, `VM.Snapshot` grant) flagged for the operator.

## Sources

- `.planning/research/STACK.md` — tmux decision + integration point, Proxmox persistence primitives + caveats, wizard no-new-deps, release-chain version confirmation, do-NOT-add list.
- `.planning/research/FEATURES.md` — table-stakes/differentiator/anti-feature per capability, MVP + priority matrix, ACC-as-UAT framing.
- `.planning/research/ARCHITECTURE.md` — named integration points (real files), new-vs-modified, seam-preserving patterns, state-machine/reconciler interactions, build order, ADR triggers.
- `.planning/research/PITFALLS-v1.3.md` — v1.3-specific pitfalls (first real-infra, wizard, persistence, first GHCR/cosign release) atop the preserved v1.0-era `PITFALLS.md` substrate.

---
*Research completed: 2026-06-24*
*Ready for roadmap: yes*
