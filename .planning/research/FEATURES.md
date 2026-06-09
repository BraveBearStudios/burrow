<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Feature Research

**Domain:** Self-hosted, browser-accessible manager for multiple concurrent Claude Code sessions running in ephemeral Proxmox LXC workers (tiling web terminal + agent-workspace lifecycle manager)
**Researched:** 2026-06-09
**Confidence:** HIGH (every feature anchored to the authoritative tech-spec / PROJECT.md; ecosystem framing from Gitpod/Coder, ttyd/GoTTY/Wetty, and the Claude Code multi-agent landscape — MEDIUM where noted)

> **Scope discipline.** Every feature below is traced to a spec capability (PROJECT.md "Active", tech-spec §5/§8/§12). Anything not in the current spec is explicitly tagged **[BEYOND CURRENT SPEC]** so it does not leak into v1 scope. The product class is the intersection of three things that no single existing tool delivers (tech-spec §1): (1) browser multi-session terminal UI, (2) ephemeral backend lifecycle, (3) reproducible per-workspace tooling. "Table stakes" is judged against that intersection, not against a bare web terminal.

## Feature Landscape

### Table Stakes (Users Expect These)

Without these, the tool is not meaningfully better than `tmux + ssh` and fails its Core Value ("create a workspace and get a live, interactive Claude Code terminal in the browser must work").

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Workspace list with live status** (creating / running / stopped / error) | The whole pitch is "watch and switch between many sessions." A manager with no live roster is not a manager. | **M** | TanStack Query polling of `GET /api/v1/workspaces` (tech-spec §8.3 `WorkspaceList`). Polling cadence + status badge mapping is the only real work. Depends on API + state machine existing. |
| **Create workspace from git repo + branch** | This is the *primary critical path* (PROJECT.md Core Value). If create fails, nothing else matters. | **L** | The create *saga*: capacity check → allocate VMID → clone template → inject cloud-init → start LXC → wait for IP → poll ttyd health → mark running (tech-spec §6.2). Failure compensation/cleanup is the hard part and must land with it (ci-cd §4.3). |
| **Live terminal streaming (WebSocket proxy)** | A workspace you can't type into is useless. The interactive Claude Code terminal *is* the product. | **L** | Browser WS → FastAPI `/ws/workspaces/{id}/terminal` → ttyd `:7681` in the LXC, bidirectional binary frames (tech-spec §6.4). nginx must hold the WS open (`proxy_read_timeout 3600s`, §10.1). |
| **Tiling multi-panel terminals** (open / split H+V / drag / resize) | "Side-by-side panels" is named in the problem statement (§1) and is the visible differentiator vs a single web terminal. Expected once you claim "multi-session." | **M** | xterm.js + react-mosaic, panel tree in Zustand `layoutStore` (§8.3). `FitAddon` must re-fit on every resize or the PTY geometry desyncs. Depends on terminal streaming. |
| **Stop / start / destroy lifecycle + enforced state machine** | Ephemeral compute is half the value prop. Users expect to reclaim RAM and to *destroy* (not just close) a workspace. | **M** | `creating→running→stopped/destroyed/error` (tech-spec §5.3). Stop preserves disk; destroy soft-deletes the row + destroys the LXC. State machine must reject illegal transitions server-side. |
| **Terminal auto-reconnect with visible overlay** | Browser tabs sleep, laptops suspend, WiFi blips. Without auto-reconnect the terminal "dies" constantly and feels broken. | **M** | Exponential backoff, 5 retries, max 30s, "reconnecting" overlay (tech-spec §8.3 `TerminalPanel`). The proxy also retries upstream internally (3×, 2s, §5.2). |
| **Per-workspace event log / activity drawer** | Boot is a multi-step async saga that can fail at any stage. Users need to see *why* a workspace is stuck in `creating` or `error`. | **S–M** | Events already modeled (tech-spec §7.1 `events`, §5.2 `GET .../events`). Backend logging is S; the expandable UI drawer is the added M (Phase 4, §12). |
| **Boot-progress states in the create flow** | Create takes tens of seconds (clone + boot + 60s ttyd timeout). A blank spinner reads as "hung." | **S** | `NewWorkspaceModal` shows "Cloning template… Starting LXC… Waiting for Claude…" (§8.3). Cheap, high perceived-quality payoff. Maps directly to saga stages. |
| **Health endpoint / dependency status** | A control plane that can't reach Proxmox or its DB must say so, not silently fail every create. | **S** | `GET /health` → `{status, db, proxmox}` (§5.2). Also feeds the navbar capacity readout. |
| **Standard response envelope + structured logging + security headers** | Cross-cutting contract (CLAUDE.md, PROJECT.md). Not a "feature" the user sees, but its absence breaks every consumer and the test contract (ci-cd §4.3 envelope snapshot). | **S** | `data`/`meta`/`error` on every `/api/v1` route; snake_case DB → camelCase JSON. Establish once in the app factory. |

### Differentiators (Competitive Advantage)

Why pick Burrow over `tmux + ssh` or a stack of raw `ttyd` instances. These align with Core Value: ephemeral, reproducible, zero-overhead-on-your-laptop multi-session management.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Ephemeral, reproducible workers** (CLAUDE.md + plugin manifest pulled fresh at boot) | "Plugin drift is impossible" (§2.3). Every session gets identical tooling from one config source — the thing GoTTY/ttyd/tmux fundamentally do not do. This is the strongest moat. | **L** | Lives in `cc-worker-config` (separate repo) + `burrow-boot.sh` (§9.3). Golden-template clone, not snowflake setup. Build-order: template must exist before any workspace can boot (Phase 0). |
| **Zero local resource overhead** (browse from any LAN device) | Run 10 agents without melting the workstation you watch from. tmux+ssh still pins load to wherever the terminals live; Burrow pushes it to owned homelab compute. | **—** (emergent) | Architectural property of the LXC-per-workspace design, not a discrete feature to build. Worth naming because it's the "why" behind the whole product. |
| **Capacity guard** (refuse create when node RAM over threshold) | Prevents the classic homelab failure: spinning up one workspace too many and OOM-ing the node, taking *all* sessions down. Protects the fleet. | **S** | `getNodeMemoryUsage()` > 0.80 → `CapacityError` (tech-spec §6.2, §12 Phase 4). Pure logic, trivially unit-testable. Surfaces in navbar ("4GB free", §8.2). |
| **Auto-stop idle workspaces** | Reclaims homelab RAM automatically; ephemeral-by-default without manual babysitting. Mirrors Gitpod's 30-min inactivity stop, which users now expect from ephemeral-workspace tools. | **M** | Detect ttyd has no active connections > N min → `status=stopped` (§12 Phase 4). **Tension with ttyd `--once`** (Open Question §2): `--once` already kills the session on tab close, so idle-detection semantics must be reconciled with the detach-vs-terminate decision. |
| **Restore / reconnect terminal after browser refresh** | A refresh shouldn't nuke a running agent. Expected from cloud IDEs; a real differentiator vs naive web terminals that lose everything on reload. | **M (with a hard caveat)** | If the workspace is still `running`, re-open the WS and rebind xterm.js (§12 Phase 4). **Architectural constraint (MEDIUM-confidence, verified):** ttyd has *no server-side replay buffer* and xterm.js scrollback is client-side only — a refreshed tab reconnects to a live PTY but **loses prior scrollback**. True scrollback restore needs `tmux`/`zellij` (or `--once` removed + a multiplexer) inside the worker. Decide v1 = "reconnect to live session, lose history" vs deferring full restore. |
| **Node selection** (pick target Proxmox node at create time) | Multi-node homelabs need to place workloads deliberately (GPU node, more-RAM node). Manual now, auto-balance later. | **S** | `node` field in `POST /api/workspaces`, dropdown in `NewWorkspaceModal` (§5.2, §8.3). Open Question §3: manual pick first, round-robin/auto-select deferred. |
| **Owned / no-commercial-dependency critical path** | AGPL/MIT all the way down (§2.4). Self-hosters who reject cloud-IDE lock-in get the agent-multiplexing UX without renting it. A positioning differentiator more than a build task. | **—** | Property of dependency choices, not a feature. Reinforces "Ownable" design principle. |
| **One-source plugin/token-proxy distribution** (rtk, caveman, gsd baked or pulled per manifest) | Every worker auto-gets token-reduction proxies + workflow plugins, optionally (boot script uses a wrapper if present, else plain `claude`, §14). Compounding cost savings across a fleet of agents. | **M** | Manifest-driven (§11). Binary/npm-global plugins baked into template; `claude-plugin` pulled fresh at boot. Lives in `cc-worker-config` (Phase 3). |

### Anti-Features (Commonly Requested, Often Problematic)

Deliberately **NOT** in v1. Each is grounded in PROJECT.md "Out of Scope" or tech-spec §13 (hosted path). Documented here to stop scope creep and re-litigation.

| Feature | Why Requested | Why Problematic (for v1) | Alternative |
|---------|---------------|--------------------------|-------------|
| **Authentication / login / users** | "It's on my network, shouldn't it have a password?" | v1 is **LAN-only single-user by design** (PROJECT.md, tech-spec §3.2). Baking auth assumptions into v1 paths contaminates the provider seams and contradicts the security posture. Auth is the *bulk* of the additive hosted path, not a bolt-on. | Network isolation (LAN/VLAN/VPN). Auth + JWT + `requireAuth` middleware ships as the hosted path (§13). **[BEYOND CURRENT SPEC for v1]** |
| **Multi-tenancy / per-user workspace ownership** | "What if my teammate wants in?" | Requires `user_id` FK on every row, row-level security, Postgres (§7.2). A full data-model rewrite if grafted onto v1 incorrectly — the seams exist precisely so it stays *additive*. | Single-operator model in v1. Multi-tenant is hosted-path scope (§13). |
| **Postgres as primary DB** | "SQLite won't scale / isn't 'real'." | ADR-0001: single-user self-host warrants **no external DB dependency**. Premature Postgres adds an ops burden with zero v1 benefit. | SQLite via `aiosqlite` behind `DbProvider`; `postgresProvider.py` stays a stub behind the seam. Swap is drop-in when hosted. |
| **Cloud / container compute backend** (Docker, K8s, serverless workers) | "Proxmox is niche; support Docker too." | v1 targets **Proxmox LXC only** (PROJECT.md). A second `ComputeProvider` impl doubles the integration + test surface before the first one is even validated against real infra. | Keep `ComputeProvider` abstract so a cloud impl is additive (§13). Don't build the second backend in v1. |
| **Real-Proxmox exercise in CI** | "Tests should hit real infra to be trustworthy." | Real Proxmox in CI is non-hermetic, slow, and flaky; it couples the pipeline to a homelab. ci-cd §2/§4.4 explicitly forbids it. | `FakeComputeProvider` + mocked Proxmox API in CI; real-infra validation happens in the dev environment (ci-cd §4.4). |
| **Native mobile app** | "I want to check agents from my phone." | A native app is a whole second client to build/ship for a single-operator tool. PROJECT.md: browser-first, responsive web only. | Responsive web UI reachable from any LAN device's browser. |
| **Secrets manager** (Vault, etc.) | "Don't put the Proxmox token in a file." | Overkill for single-host self-host; adds a dependency and bootstrap problem. | Gitignored `.env`, `.env.example` template only (PROJECT.md). Secrets manager is hosted-path scope. |
| **Built-in file editor / IDE / VS Code-in-browser** | "Make it a full cloud IDE." | Massively expands scope and competes with Gitpod/Coder/code-server. Burrow's job is *agent terminal* management, not an IDE. The agent edits files inside the worker. | The terminal *is* the interface; Claude Code does the editing. Keep Burrow a session manager. **[BEYOND CURRENT SPEC]** |
| **Terminal sharing / collaboration / multi-viewer** | "Let two people watch one session." | Implies presence, conflict handling, and (realistically) auth — none of which exist in single-user v1. ttyd's multi-client story is also weak. | Single operator, single viewer per session in v1. Revisit with the hosted/multi-tenant path. **[BEYOND CURRENT SPEC]** |
| **Persistent / snapshotted workspaces ("save my env")** | "Don't make me re-clone every time." | Directly contradicts the **"Ephemeral by default / no snowflake state"** design principle (§2.2). Reproducibility *is* the value; durable per-workspace state erodes it. | `stop` already preserves LXC disk for restart (§5.2). Reproducibility comes from `cc-worker-config`, not from hoarding workspace state. |
| **Full scrollback history restore across reconnect** | "I refreshed and lost everything above the fold." | Architecturally blocked in v1: ttyd has no server-side replay buffer; xterm.js scrollback is client-side. Delivering it means injecting tmux/zellij into the worker template — real work, not in the current spec. | v1: reconnect to the *live* session (history may be lost). Full restore is a worker-template enhancement. **[BEYOND CURRENT SPEC; tie to Open Question §2]** |
| **Auto node selection / load balancing** | "Just put it on the least-loaded node." | Premature optimization for a 1–2 node homelab; the capacity guard already prevents the worst outcome (OOM). | Manual node pick in v1 (Open Question §3); round-robin/auto-select deferred to a later phase. **[BEYOND CURRENT SPEC for v1 default]** |

## Feature Dependencies

```
Golden Template LXC (Phase 0)
    └──required-by──> Create-workspace saga
                          ├──requires──> Capacity guard (precondition of create)
                          ├──requires──> Boot-progress states (UX of the saga)
                          └──required-by──> Live terminal streaming (WS proxy)
                                                ├──requires──> Stop/start/destroy + state machine
                                                │                  (proxy refuses if status != running)
                                                ├──required-by──> Tiling multi-panel terminals
                                                │                     └──enhances──> Workspace list (open panel from roster)
                                                ├──required-by──> Auto-reconnect overlay
                                                │                     └──required-by──> Restore-after-refresh
                                                └──required-by──> Event log (terminal.connected/disconnected)

Response envelope + structured logging + health   ──underpins──>  every API-backed feature

Reproducible workers (cc-worker-config)  ──enhances──>  Create-workspace saga
                                          (pulled by burrow-boot.sh at boot)

Auto-stop idle  ──conflicts/tension──>  ttyd --once (detach-vs-terminate, Open Q §2)
Restore-after-refresh  ──limited-by──>  ttyd no-replay-buffer (scrollback lost)
```

### Dependency Notes

- **Everything requires the golden template (Phase 0).** No workspace can boot, stream, or be tested against real infra until the template LXC + `provision-template.sh` + `burrow-boot.sh` exist. This is why Phase 0 is first in tech-spec §12.
- **Live terminal streaming requires the create saga + state machine.** The WS proxy refuses unless `status == running` and needs `lxcIp` (tech-spec §6.4). So: API/saga before terminal.
- **Tiling panels require terminal streaming, not vice-versa.** A panel is a container for a `TerminalPanel`; build a single working terminal first, then the mosaic layout (matches §12 Phase 2 ordering).
- **Restore-after-refresh requires auto-reconnect.** Restore is "reconnect, but triggered by page load instead of a dropped socket" — same WS-rebind machinery, so reconnect lands first (both in §12 Phase 4).
- **Auto-stop-idle has a tension with `--once`, not a clean dependency.** `--once` terminates the session on disconnect; idle-stop assumes the session survives disconnect so it can later be stopped. These two must be reconciled (Open Question §2) before either is finalized — flag for the roadmap.
- **Restore-after-refresh is limited by a ttyd property, not a missing feature.** No server replay buffer ⇒ v1 restore reconnects to a live PTY but cannot replay lost scrollback. Decide the acceptable v1 behavior up front so it isn't mistaken for a bug.
- **Capacity guard is a precondition inside create, not a separate user flow.** It runs as step 1 of the saga (§6.2) and also feeds the navbar readout; cheap, build with create.
- **Response envelope / logging / health underpin everything** and should be established in the app factory in Phase 1 before routers proliferate (avoids retrofitting the contract).

## MVP Definition

### Launch With (v1) — the spec's Phases 0–3 plus the cheap-but-essential Phase 4 items

The bar: satisfy Core Value end-to-end — create from a repo, get a live terminal, manage its lifecycle, in a tiling browser UI, with reproducible workers.

- [ ] **Golden template + worker boot pipeline** — nothing boots without it (Phase 0).
- [ ] **Create-from-git saga with boot-progress + capacity guard** — the critical path; capacity guard is S and prevents fleet-wide OOM, so include it now (Phases 1 + 4 capacity item).
- [ ] **Live WebSocket terminal streaming** — the product is the interactive terminal (Phase 1).
- [ ] **Workspace list with live status** — you can't manage what you can't see (Phase 2).
- [ ] **Stop / start / destroy + enforced state machine** — ephemeral lifecycle is the value prop (Phase 1 API + Phase 2 controls).
- [ ] **Tiling multi-panel terminals (open/split/drag/resize)** — the "multi-session" claim (Phase 2).
- [ ] **Auto-reconnect with overlay** — without it the terminal feels broken on every blip (Phase 2).
- [ ] **Boot-progress states in create modal** — S cost, large perceived-quality win (Phase 2).
- [ ] **Reproducible workers (CLAUDE.md + plugins at boot)** — the strongest differentiator (Phase 3).
- [ ] **Response envelope + structured logging + health + security headers** — cross-cutting contract (Phase 1).
- [ ] **Event log (backend) + activity drawer (UI)** — needed to debug failed boots (Phase 4; backend is S, drawer is M).
- [ ] **Node selection (manual)** — multi-node placement; S (Phase 2 form field).

### Add After Validation (v1.x)

Once the critical path is proven on real infra.

- [ ] **Auto-stop idle workspaces** — add once `--once`/detach semantics are decided (Open Q §2); reclaims RAM automatically.
- [ ] **Restore-after-refresh (live-session reconnect, no scrollback)** — ship the limited version first; it's the honest v1 behavior given ttyd's no-replay constraint.
- [ ] **Full activity-drawer polish / event filtering** — once the event taxonomy is exercised in anger.

### Future Consideration (v2+ / hosted path)

Defer until the single-operator product is validated.

- [ ] **Auto node selection / round-robin balancing** — Open Q §3; only valuable past ~2 nodes. **[BEYOND CURRENT SPEC default]**
- [ ] **Full scrollback restore via tmux/zellij in the worker** — worker-template enhancement; real work. **[BEYOND CURRENT SPEC]**
- [ ] **Auth + multi-tenancy + Postgres + cloud compute** — the entire hosted path (tech-spec §13). **[BEYOND CURRENT SPEC]**
- [ ] **Detach-vs-terminate UX distinction** — resolves Open Q §2 into a real UI affordance once semantics settle.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Create-from-git saga (+ boot progress) | HIGH | HIGH | **P1** |
| Live WebSocket terminal streaming | HIGH | HIGH | **P1** |
| Golden template + boot pipeline | HIGH | HIGH | **P1** |
| Workspace list + live status | HIGH | MEDIUM | **P1** |
| Stop/start/destroy + state machine | HIGH | MEDIUM | **P1** |
| Tiling multi-panel terminals | HIGH | MEDIUM | **P1** |
| Auto-reconnect overlay | HIGH | MEDIUM | **P1** |
| Response envelope / logging / health | MEDIUM (HIGH if missing) | LOW | **P1** |
| Capacity guard | MEDIUM | LOW | **P1** |
| Reproducible workers (plugins/CLAUDE.md) | HIGH | HIGH | **P1** |
| Node selection (manual) | MEDIUM | LOW | **P1** |
| Event log + activity drawer | MEDIUM | MEDIUM | **P2** |
| Auto-stop idle | MEDIUM | MEDIUM | **P2** |
| Restore-after-refresh (live, no scrollback) | MEDIUM | MEDIUM | **P2** |
| Auto node selection / balancing | LOW | MEDIUM | **P3** |
| Full scrollback restore (tmux) | MEDIUM | HIGH | **P3** |
| Auth / multi-tenant / Postgres / cloud | (hosted) | HIGH | **P3** |

**Priority key:** P1 = must have for launch · P2 = should have, add when possible · P3 = future / hosted-path.

## Competitor Feature Analysis

Burrow sits at an intersection no single tool occupies (tech-spec §1). Comparison is against the nearest analogues in each axis.

| Feature | tmux + ssh (status quo) | Bare ttyd / GoTTY / Wetty | Gitpod / Coder (cloud IDE) | Burrow's Approach |
|---------|-------------------------|---------------------------|----------------------------|-------------------|
| Browser multi-session UI | None (terminal-only) | One terminal per process; no roster/tiling | Full IDE, tabbed terminals | Tiling xterm.js panels + workspace roster (web, LAN) |
| Ephemeral backend lifecycle | Manual (you manage processes) | None (just exposes a TTY) | Yes (create/stop/destroy, auto-stop) | Yes — Proxmox LXC clone/start/stop/destroy + state machine |
| Reproducible per-session tooling | None (snowflake shells) | None | `.gitpod.yml` / devcontainer | Golden template + `cc-worker-config` manifest pulled at boot |
| Auto-stop idle | No | No | Yes (30-min default) | Yes (Phase 4; reconciled with `--once`) |
| Reconnect / session persistence | tmux survives drops + full scrollback | Lost on disconnect (no replay buffer) | Full restore (server-side) | Auto-reconnect to live session; **scrollback not restored in v1** (ttyd constraint) |
| Capacity / resource guard | None | None | Platform-managed quotas | Node RAM threshold guard before create |
| Self-host / ownable | Fully | Fully | Self-host possible (heavy) | Fully self-host; AGPL/MIT critical path |
| Auth / multi-user | OS / ssh keys | None by default | Yes (core) | **None in v1 by design** (LAN-only); hosted path adds it |

**Read:** Burrow beats bare ttyd/GoTTY on lifecycle + reproducibility + roster; beats tmux+ssh on browser UX + zero-local-overhead + reproducibility; deliberately under-scopes Gitpod/Coder by *not* being an IDE and *not* doing auth/multi-tenant — that narrower scope is the point, and the provider seams keep the cloud-IDE-grade capabilities as an additive path rather than a v1 burden.

## Sources

- **Authoritative (HIGH):** `E:\repos\burrow\.planning\PROJECT.md`; `E:\repos\burrow\docs\tech-spec.md` (§1 problem, §2 principles, §5 API + state machine, §6 backend, §7 data model, §8 UI contracts, §9 template/boot, §11 plugins, §12 phases, §13 hosted path); `E:\repos\burrow\docs\ci-cd-and-testing.md` (§2 images, §4 test tiers, what is in-/out-of-CI-scope).
- **Ecosystem framing (MEDIUM):**
  - [GoTTY — share your terminal as a web application](https://github.com/yudai/gotty) and [ttyd](https://github.com/sorenisanerd/gotty) / [16 self-hosted web terminals](https://medevel.com/16-list-self-hosted-terminals/) — establishes "bare web terminal" baseline and the one-process-per-connection model.
  - [Gitpod Workspace Lifecycle](https://www.gitpod.io/docs/configure/workspaces/workspace-lifecycle) — ephemeral create/start/stop/destroy + 30-min inactivity auto-stop as the user-expected baseline for ephemeral-workspace tools.
  - [Persistent terminal sessions: tmux vs zellij](https://agents-ui.com/blog/persistent-terminal-sessions-tmux-zellij-guide/) and [Termix: native tmux integration for session persistence + scrollback](https://github.com/Termix-SSH/Support/issues/617) — verifies the web-terminal scrollback/replay-buffer constraint behind the restore-after-refresh caveat.
  - [Orchestrate teams of Claude Code sessions (official docs)](https://code.claude.com/docs/en/agent-teams) and [Shipyard: multi-agent orchestration for Claude Code](https://shipyard.build/blog/claude-code-multi-agent/) — confirms the "manage many parallel Claude Code sessions" problem space Burrow targets.

---
*Feature research for: self-hosted multi-session browser terminal / ephemeral Claude Code workspace manager (Burrow)*
*Researched: 2026-06-09*
