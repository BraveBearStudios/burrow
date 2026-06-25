<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Feature Research — Burrow v1.3 "Go Live"

**Domain:** Self-hosted homelab tooling — infra-setup onboarding + persistent/resumable terminal workspaces
**Researched:** 2026-06-24
**Confidence:** HIGH (grounded in the existing Burrow surfaces — `health.py`, `NewWorkspaceModal.tsx`, `TerminalPanel.tsx`, `useTerminal.ts`, `burrow-boot.sh` — plus MEDIUM external sources on wizard + session-persistence UX)

> Scope discipline: this is a SUBSEQUENT milestone. Existing v1.0–v1.2 features (workspace CRUD,
> tiling terminals, detach/reconnect overlay, stop/start UI, activity drawer, auto node selection,
> capacity guard, reaper/auto-stop) are NOT re-researched. Only the THREE v1.3 additions are below:
> (1) setup wizard, (2) real-boot v2 persistence (WSX-02), (3) scrollback restore (WSX-03). The
> fourth v1.3 item — real-infra acceptance (ACC-01/02/03) — is UAT, not a buildable feature; framed
> as such in its own section so it is not turned into REQ-IDs that imply new code.

## Feature Landscape

### Feature 1 — In-app Setup Wizard (guided Proxmox onboarding)

The "Burrow is not configured yet" first-run flow: connect + validate a Proxmox host/token, verify the
golden template exists, run a health-check, and land the first workspace. The control plane already
exposes the spine for this — `/api/v1/health` returns per-dependency `compute: ok|error` and degrades
to 200 (never 500), so a "compute unreachable" state is already a first-class, non-crashing signal.

#### Table Stakes (operators expect these)

| Feature | Why Expected | Complexity | Notes / Dependency |
|---------|--------------|------------|--------------------|
| **"Not configured yet" gate** on first run | Every connect-an-external-system tool (Jira, AdGuard Home, JFrog, Home Assistant) opens on a setup screen, not a broken dashboard. Burrow today would render an empty workspace list + silent create failures if Proxmox is unreachable. | LOW | Drive off the **existing `/api/v1/health` `compute` field** — `error` (+ unset token) → route to wizard. No new "is-configured" concept needed; reuse the degrade signal. |
| **Test-connection step** (host + token → reachable?) | The universal first wizard step. Operators expect a "Test connection" button with a clear pass/fail before anything is provisioned. | LOW–MEDIUM | New `POST /api/v1/setup/test-connection`; wraps an existing `ComputeProvider.healthcheck()`-style probe. CI-provable over the **Fake compute provider**. |
| **Validate-permissions / preflight** (token has the right ACLs?) | A reachable host with a wrong-scoped token fails later, opaquely (mid-create). Good wizards check ACLs/role up front. Burrow's priming kit already defines the exact least-priv ACL set. | MEDIUM | Probe the role/ACL scope (template VMID, pool, storage, node) via the provider. Surface "token reachable but missing X" distinctly from "unreachable". The PVE-side user/role/token CREATION stays operator-run (per PROJECT.md) — the wizard **validates a provided token and guides the manual `host-prime` steps**, it does not silently create them. |
| **Verify golden template exists** | A valid token but no template VMID 9000 = every create fails. Operators expect the wizard to confirm the template is present + is a template (not a running CT). | MEDIUM | Query the configured `TEMPLATE_VMID`; report present/absent/not-a-template. If absent, link to the `host-prime` template steps rather than attempting to build it from the browser. |
| **Per-step status + actionable failure** | Wizards live or die on this: each step shows ✓ / ⟳ / ✕, and a failure shows *what* failed and *the next action* (not a stack trace). | LOW (UI) | **Reuse the `NewWorkspaceModal` saga pattern verbatim** — `SAGA_STEPS` checklist (✓/⟳/○/✕), `--err` strip, server message surfaced verbatim, `aria-live`. This component already implements every state the wizard needs. |
| **Land the first workspace** as the terminal step | Onboarding should end in the core value, not a config screen. The wizard's success state should hand off into "create your first workspace". | LOW | Reuse `NewWorkspaceModal` + `layoutStore.openPanel(id)`. The wizard's final step IS the create modal. |
| **Re-runnable / idempotent steps** | Operators retry. Re-running test-connection or template-verify must be safe and converge to the same result, never duplicate side effects. | LOW | All wizard probes are **read-only** (health, ACL query, template query) — idempotent by construction. No checkpoint machinery needed because nothing is mutated. |
| **Resumability (resume at first failing step)** | If the operator fixes a token and re-opens, the wizard should re-evaluate and land on the first unmet prerequisite, not force a linear re-walk. | LOW–MEDIUM | Because steps are read-only probes, "resume" = re-run all probes on open and highlight the first failing one. No persisted wizard state required (this is the simplest correct design). |

#### Differentiators (nice, not required)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Copy-paste `host-prime` command hints** in the failure path | Turns "token missing ACL on /pool/burrow-workers" into a one-click-copy `pvesh`/script line. Closes the loop without leaving the browser. | LOW | Static, derived from the existing `host-prime` scripts. High value-to-cost; strong fit for a single-operator homelab tool. |
| **Live re-check after a fix** ("Recheck" button per failed step) | Operator edits `.env`/runs a script in another tab, clicks Recheck, sees it flip to ✓ without a full restart. | LOW | Just re-invokes the read-only probe. |
| **Settings page "re-run setup"** entry point | Most setup wizards (Jira, Home Assistant) hide forever after first run; operators then can't re-validate after a Proxmox change. A non-destructive "verify configuration" view is genuinely useful. | LOW | Reuse the same probe panel outside the gate. |

#### Anti-Features (avoid — scope creep risks)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Browser-side Proxmox user/role/token CREATION** | "Why make me run scripts? Just set it up for me." | Requires `root@pam` in the wizard's blast radius, contradicts the least-priv design (PROJECT.md explicitly keeps PVE-side creation operator-run), and is a security footgun on a no-auth LAN tool. | Wizard **validates** a provided token + **links/copies** the `host-prime` steps. Guide, don't automate around. |
| **Building the golden template from the browser** | "Verify-or-create" feels complete. | Template build is a multi-minute, `pct`-over-SSH, node-side operation outside the HTTPS `ComputeProvider` seam (boot-config ADR already established `pct exec`/`pct push` aren't in the API). Leaks node specifics past the seam. | Verify presence; deep-link to `20-create-template.sh`. |
| **Persisting secrets the wizard collects into a DB/secrets store** | "Save my token so I don't re-enter it." | v1 secret store is the gitignored `.env` by design; a new secrets path is hosted-path scope (out of scope per PROJECT.md). | Token lives in `.env`; the wizard reads/validates, never re-stores. |
| **Multi-step DB-persisted wizard state machine w/ checkpoints** | Generic onboarding advice ("checkpoint resumable steps"). | Burrow's steps are read-only probes — there is no partial mutation to recover from. A persisted checkpoint machine is complexity with no payload here (YAGNI). | Re-run probes on open; land on first failing step. |
| **Editing arbitrary settings inside the wizard** (pool ranges, timeouts, subnet) | "While I'm here, configure everything." | Bloats a focused connect→verify→first-workspace flow into a settings sprawl; those values are `.env`-driven and rarely changed. | Keep the wizard to the connect/verify/first-workspace path; settings stay in `.env`. |

### Feature 2 — Real-boot v2 Persistence (WSX-02: workspaces survive stop/start)

Today the worker is **ephemeral by design** (Design Principle 2: "gone when destroyed"), but the state
machine already distinguishes **stop** (`/stop` "preserves disk state", → `stopped`) from **destroy**
(`DELETE` → `destroyed`, "gone for good"). The stop/start UI, the `stopped` placeholder, and the
`useStop/useStartWorkspace` hooks already ship. WSX-02 makes "stop preserves the workspace" actually
true on real infra (filesystem survives; the CT is stopped, not deleted) and start brings the same CT
back.

#### Table Stakes (operators expect these once stop/start is surfaced)

| Feature | Why Expected | Complexity | Notes / Dependency |
|---------|--------------|------------|--------------------|
| **Stop = pause, keep the filesystem** (CT stopped, not destroyed) | The `TerminalPanel` `stopped` copy literally promises "pick up where you left off"; the `/stop` spec says "preserves disk state". An operator who clicks Stop and loses their cloned repo + working tree would consider it a bug. | MEDIUM | Real-infra: `stopLxc` (not `destroyLxc`); the cloned CT's rootfs persists on the node. **Depends on the existing state machine** (`running`→`stopped`→`running`) — already enforced, this makes it real. |
| **Start = same CT comes back** (same VMID, same disk, repo intact) | "Resume" means the literal same workspace, not a fresh clone. | MEDIUM | `startLxc` on the persisted VMID; re-wait for ttyd health (reuse the existing `_waitForTtyd` poll). Boot re-runs `burrow-boot.sh` — must be **idempotent over an already-cloned repo** (don't re-clone over a dirty tree). |
| **Clear stop-vs-destroy distinction in the UI** | The single most dangerous confusion in any "resumable" tool: did Stop delete my work? Burrow already separates them (Stop = reversible no-confirm; Terminate = confirm-gated "gone for good"). | LOW (already built) | No new UI; v1.3 must **preserve** this separation and make the Stop promise true on real infra. The confirm-gated Destroy copy stays the only destructive path. |
| **Capacity accounting reflects stopped workspaces** | A stopped CT holds disk but (largely) frees RAM. The capacity guard + node-select must treat stopped vs running correctly so a homelab doesn't over- or under-count. | MEDIUM | Touches the existing capacity guard / auto-select seam (`getNodeMemory`). Flag for phase-level care — interacts with reaper + auto-stop. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Snapshot-based persistence** (Proxmox CT snapshot on stop) | Lets a stopped workspace roll back to a known-good point; stronger than plain stop. | HIGH | Likely OVERKILL for v1.3's "survive stop/start" goal. Plain stop (disk persists) meets the table stake; snapshots add a restore-point feature nobody asked for yet. Note as v1.x. |
| **"Stopped N hours ago" + disk-still-held indicator** | Helps the operator reason about what's parked vs running and what to clean up. | LOW | The `stopped` placeholder + activity drawer already exist; a timestamp / "disk retained" line is a small additive touch. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Keeping running processes alive across stop** ("freeze the Claude session, thaw it later") | "Resume exactly where I left off" sounds like the process keeps running. | A stopped CT halts all processes; live process freeze (CRIU-style) is fragile, not a Proxmox-LXC table stake, and far out of scope for a go-live milestone. Promising it sets a false expectation. | Stop halts the session; start re-execs Claude fresh in the **preserved filesystem** (repo + edits intact). Scrollback restore (WSX-03) covers the *visible* continuity. |
| **Infinite-retention stopped workspaces** | "Never lose anything." | Stopped CTs hold disk on a finite homelab; unbounded parked workspaces silently exhaust the node. | Stop is reversible but the operator still owns destroy; the existing reaper/auto-stop ethos applies. (A retention / auto-destroy-of-long-stopped policy is a deliberate later decision, not an assumed feature.) |
| **Auto-start on access** ("click a stopped panel → it boots") | Convenient. | Hidden multi-minute boot + capacity spend triggered by a stray click; surprising resource use on shared homelab RAM. | Explicit **Start** CTA (already in the `stopped` placeholder + header). Keep the boot operator-initiated. |

### Feature 3 — Scrollback Restore (WSX-03)

The precise nuance the question asks for. There are THREE distinct levels here, and Burrow already has
level 1. The worker runs **persistent ttyd** (`burrow-boot.sh`: no `--once`, `bash -lc "... exec claude"`)
and the browser re-creates a fresh `xterm.Terminal` on each mount (`useTerminal.ts`).

| Level | Behavior | Status in Burrow | Category |
|-------|----------|------------------|----------|
| **L1 — Reattach to a LIVE session** (browser disconnect/refresh, worker still running) | Reconnect the WS; ttyd replays its server-side buffer into the fresh xterm; the live PTY continues. | **ALREADY SHIPPED.** `useTerminal` detach/reattach + reconnecting overlay; ttyd persistent so the PTY survives a tab close. | **Table stakes — already met.** Don't re-spend on it; just don't regress it. |
| **L2 — Replay HISTORY after a worker reboot** (stop→start: the PTY process died, scrollback is gone) | After WSX-02 start, the new ttyd/PTY is empty — the prior session's scrollback does NOT come back for free. Restoring it requires a multiplexer in the worker that serializes scrollback to disk (which survives the stop) and replays on reattach. | **NOT met today** (no tmux/zellij in `burrow-boot.sh`; plain `exec claude`). This is the actual WSX-03 work. | **Differentiator.** This is what makes stop/start feel like "resume" rather than "fresh boot". |
| **L3 — Resume the running process mid-execution** (Claude keeps generating across the reboot) | Process state survives a reboot. | Not feasible on stopped LXC. | **Out of scope / anti-feature** (see WSX-02 anti-features). |

#### Table Stakes

| Feature | Why Expected | Complexity | Notes / Dependency |
|---------|--------------|------------|--------------------|
| **L1 live reattach with buffer replay** | Refreshing the browser and seeing your session as you left it is the baseline of any web terminal. | DONE | Preserve in v1.3 regression tests. **Depends on:** persistent ttyd (worker) + `useTerminal` reconnect + reconnecting overlay — all shipped. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes / Dependency |
|---------|-------------------|------------|-------|
| **L2 scrollback survives a stop/start** (multiplexer serializes scrollback to the persisted disk) | Turns WSX-02's "same CT" into a felt "same session" — start a stopped workspace and your prior transcript is right there. The headline payoff of the persistence pair. | HIGH | **Zellij** does this natively: `pane_viewport_serialization=true` + `scrollback_lines_to_serialize=N` serializes scrollback to a cache dir that survives a CT stop; on reattach it restores layout + scrollback. **tmux** needs `tmux-resurrect`/`tmux-continuum` plugins for the same. Either way the worker boots into the multiplexer and ttyd attaches to it. **Hard dependency on WSX-02** (the disk must persist for the serialized scrollback to survive). |
| **Bounded scrollback restore** (cap restored lines, e.g. last N) | Honest, resource-safe "resume" without dragging an unbounded transcript across reboots. | LOW (config of L2) | Set `scrollback_lines_to_serialize` to a finite N (NOT 0/all). This is the anti-feature mitigation baked into the differentiator. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Infinite-retention / unbounded scrollback** | "Keep my whole history forever." | Zellij's own docs warn full serialization (`scrollback_lines_to_serialize=0`) raises CPU + cache-folder disk use; on a homelab worker that is real cost for marginal value. | Serialize a **bounded** last-N lines. Felt-continuity, capped cost. |
| **Auto-re-running the resurrected command** (Claude auto-restarts on reattach) | "Just pick up exactly where I was." | Auto-executing a resurrected command is a known footgun — Zellij deliberately gates it behind a "Press ENTER to run" banner to avoid accidents (e.g. a destructive command replays). | Restore the *transcript* (visible scrollback); let the operator re-issue commands. Continuity is visual, not a silent re-exec. |
| **Server-side (control-plane) scrollback recording** | "Record terminals centrally so I can scroll back even with the worker off." | Puts the control plane in the business of storing per-session terminal logs (storage growth, redaction, retention, a new data class on a no-auth box). Out of proportion to the goal. | Keep scrollback in the worker's multiplexer on the worker's persisted disk. The control plane stays a relay (matches the existing dumb-bridge proxy design). |

## Feature Dependencies

```
Setup Wizard
    └──reuses──> NewWorkspaceModal saga (✓/⟳/○/✕ + --err strip + aria-live)   [SHIPPED]
    └──reads────> /api/v1/health  compute: ok|error  (degrade-not-500)         [SHIPPED]
    └──ends in──> Create-first-workspace (openPanel)                            [SHIPPED]

WSX-02 Persistence (stop keeps the CT + disk; start brings it back)
    └──requires──> Workspace state machine running<->stopped (+ stop/start UI)  [SHIPPED]
    └──requires──> stopLxc/startLxc (not destroy) on real infra                 [NEW, real]
    └──touches────> capacity guard / auto node-select (stopped vs running RAM)  [SHIPPED seam]

WSX-03 Scrollback Restore
    |-- L1 live reattach --reuses--> useTerminal reconnect + persistent ttyd    [SHIPPED]
    └-- L2 reboot replay --REQUIRES--> WSX-02 (disk must persist)               [HARD DEP]
                         --requires--> multiplexer in burrow-boot.sh (worker)   [NEW, worker repo]
                         --reuses----> reconnecting overlay on start re-wait     [SHIPPED]

ACC-01/02/03 (UAT) --validates--> all of the above on real Proxmox/GHCR        [NOT code]
```

### Dependency Notes

- **WSX-03-L2 requires WSX-02:** scrollback is serialized to the worker's disk; if stop destroys the disk (today's ephemeral model), there is nothing to restore. Persistence must land first or in lockstep. **Order WSX-02 before/with WSX-03.**
- **Setup wizard depends on nothing new** — it is almost entirely a recomposition of shipped surfaces (`/health`, the saga checklist, the create modal). Lowest-risk of the three; can lead.
- **WSX-03-L2 lives in the `cc-worker-config` repo** (the worker `burrow-boot.sh` + multiplexer config), NOT the control-plane repo. Cross-repo dependency — flag for the operator (worker reproducibility already depends on the second repo).
- **WSX-02 touches the capacity / auto-select seam** — a stopped CT changes the RAM math. This is the one place persistence brushes existing logic; phase it with care.

## MVP Definition

### Launch With (v1.3 "Go Live")

- [ ] **Setup wizard: gate + test-connection + permission/template verify + first workspace** — the go-live story is "a new operator points Burrow at their Proxmox and gets a terminal." Table-stakes for "Go Live". Read-only probes only; reuse the saga UI.
- [ ] **WSX-02 stop-keeps-the-CT / start-brings-it-back on real infra** — makes the already-shipped Stop UI's promise true. Without it, "stop" is a lie on real hardware.
- [ ] **WSX-03-L2 bounded scrollback restore after stop/start** (worker multiplexer) — the differentiator that makes persistence felt; bounded line count to stay homelab-safe.
- [ ] **Preserve L1 live reattach** — regression-guard the shipped behavior; no new build.
- [ ] **(UAT, not a feature) ACC-01/02/03 real-infra acceptance** — operator-run smoke; see framing below.

### Add After Validation (v1.x)

- [ ] **Snapshot-based persistence / restore points** — once plain stop/start persistence is proven valuable on real infra.
- [ ] **"Re-run setup / verify configuration" settings view** — after the first-run wizard ships and operators ask to re-validate post-change.
- [ ] **Retention policy for long-stopped workspaces** (auto-destroy after N days parked) — once real disk-pressure data exists.

### Future Consideration (v2+)

- [ ] **Browser-driven template / identity provisioning** — only if the security model changes (it shouldn't in self-host v1).
- [ ] **Centralized session recording / audit** — hosted-path territory, needs auth + retention design.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Setup wizard: gate + test-connection + verify + first workspace | HIGH | LOW–MEDIUM (recompose shipped surfaces) | P1 |
| WSX-02 stop-keeps-CT / start-restores on real infra | HIGH | MEDIUM | P1 |
| WSX-03-L2 bounded scrollback restore (worker multiplexer) | HIGH | HIGH (cross-repo worker change) | P1 |
| Preserve L1 live reattach (regression guard) | HIGH | LOW (already built) | P1 |
| Wizard copy-paste `host-prime` hints + per-step Recheck | MEDIUM | LOW | P2 |
| Snapshot-based persistence | LOW (for now) | HIGH | P3 |
| "Re-run setup" settings view | MEDIUM | LOW | P2 |
| Retention policy for stopped workspaces | MEDIUM | MEDIUM | P3 |

**Priority key:** P1 must-have for go-live · P2 should-have, add when possible · P3 future.

## Real-Infra Acceptance (ACC-01/02/03) — UAT, NOT a buildable feature

> **Framed deliberately per the quality gate.** ACC-01/02/03 is *validation that the v1.3 code works on
> real hardware*, not a code feature. It must NOT be turned into REQ-IDs that imply new application code.
> It is an operator-run, human-UAT checklist (`docs/test-it-out-checklist.md`, the per-phase
> `*-HUMAN-UAT.md` files, and the ★-marked items in PROJECT.md).

- **ACC-01 (real Proxmox):** the create→terminal→stop→start→destroy gate on real CTs, plus reaper /
  auto-stop / capacity / multi-node auto-select under real load. This is where WSX-02 + WSX-03-L2 are
  *proven* (CI proves them only over the Fake provider).
- **ACC-02 (first live CI + release):** first release-please PR → tag → publish; `harden-runner` egress
  block-flip from discovered audit telemetry.
- **ACC-03 (supply-chain):** real GHCR publish + `cosign verify` + `gh attestation verify`.

These map to REQ-IDs only as **acceptance criteria / UAT checklist items**, with the verification path =
"operator-run on real homelab/GHCR", never CI. Burrow's design (CI over the Fake, real-infra in dev) is
explicit on this (PROJECT.md Out-of-Scope: "Real-Proxmox exercise in CI"). The downstream requirements
step should record these as UAT gates, not as new features to build.

## Competitor / Prior-Art Feature Analysis

| Feature | Prior art | Our approach |
|---------|-----------|--------------|
| First-run setup gate | AdGuard Home initial-config wizard; JFrog onboarding wizard; Jira setup wizard (one-time, hides after) | Gate off the existing `/health` degrade signal; keep a non-destructive re-verify path so it isn't a one-shot. |
| Test-connection / preflight before provisioning | Generic "validate config before apply; check before mutating" (config-endpoint best practice) | Read-only probes (health, ACL, template) before any create; surface unreachable vs wrong-scope distinctly. |
| Resumable / idempotent onboarding | Checkpointed `--resume` onboarding flows; re-run-doesn't-wipe wizards | Burrow's probes are read-only → idempotent by construction; "resume" = re-probe on open, land on first failure. No checkpoint store (YAGNI). |
| Scrollback survives reboot | Zellij session-resurrection (`pane_viewport_serialization` + `scrollback_lines_to_serialize`); tmux-resurrect / continuum | Worker multiplexer serializes a **bounded** scrollback to the persisted disk; restore transcript on start, never auto-re-run the command. |

## Sources

- Existing Burrow surfaces (HIGH — read directly): `api/routers/health.py` (degrade-not-500 `compute` field), `ui/src/components/NewWorkspaceModal.tsx` (saga checklist pattern), `ui/src/components/TerminalPanel.tsx` (`stopped` placeholder + Start CTA + terminate confirm), `ui/src/hooks/useTerminal.ts` (reconnect / reattach / detach), `cc-worker-config/lxc/worker-template/burrow-boot.sh` (persistent ttyd, no `--once`, plain `exec claude`), `docs/tech-spec.md` §5.2/§5.3 (stop preserves disk; state machine), `docs/test-it-out-checklist.md` (ACC-01/02/03 UAT), `.planning/PROJECT.md` (scope, out-of-scope, validated features).
- Zellij Session Resurrection docs (MEDIUM — official): https://zellij.dev/documentation/session-resurrection.html — layout + scrollback serialization, `pane_viewport_serialization`, `scrollback_lines_to_serialize` (0 = all, warned costly), resurrected commands gated behind "Press ENTER to run" (no auto-exec).
- AdGuard Home initial configuration wizard (MEDIUM): https://deepwiki.com/AdguardTeam/AdGuardHome/1.2-initial-configuration-wizard
- JFrog Platform onboarding wizard (MEDIUM): https://docs.jfrog.com/installation/docs/onboarding-wizard
- Jira setup wizard, one-time + console-configurable thereafter (MEDIUM): https://confluence.atlassian.com/adminjiraserver0906/running-the-setup-wizard-1217304560.html
- Home Assistant "re-run onboarding wizard" discussion (LOW): https://github.com/home-assistant/architecture/issues/228
- Persistent terminal sessions / tmux vs zellij overview (MEDIUM): https://agents-ui.com/blog/persistent-terminal-sessions-tmux-zellij-guide/

---
*Feature research for: Burrow v1.3 "Go Live" — setup wizard, real-boot v2 persistence, scrollback restore (+ ACC UAT framing)*
*Researched: 2026-06-24*
