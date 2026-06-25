<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Architecture Research — v1.3 "Go Live" Integration

**Domain:** Self-hosted control plane (FastAPI + Proxmox LXC) — SUBSEQUENT milestone, integrating three NEW capabilities into the shipped v1.2 architecture.
**Researched:** 2026-06-24
**Confidence:** HIGH (grounded in the actual `api/` source, ADR-0001..0010, and the worker boot script; no external library claims load-bearing here)

## Scope & Method

This is integration research, not a redesign. The three v1.3 features (setup wizard, real-boot v2 persistence, real-infra acceptance) attach to an existing, well-factored control plane. Every recommendation below names the real file it touches and marks each piece **NEW** or **MODIFIED**. Everything stays behind the two existing seams (`ComputeProvider`, `DbProvider`) so it remains CI-provable over `FakeComputeProvider` (acceptance is the only human-UAT piece).

The load-bearing facts the existing code establishes (all verified in source):

- The create lifecycle is one saga in `api/services/workspaceService.py::createWorkspace` (8 steps; capacity+reserve under `self._create_lock`, then clone→persist-intent→start→getIp→wait_ttyd→running).
- The state machine is a single explicit table in `api/lib/statemachine.py::TRANSITIONS` — adding a state means adding rows here and nothing else changes the policy authority.
- The compute seam is `api/compute/provider.py::ComputeProvider` (ABC), with `FakeComputeProvider` (`api/compute/fakeProvider.py`) and `ProxmoxComputeProvider` (`api/compute/proxmoxProvider.py`). The seam-leakage test (`api/tests/unit/test_seam_leakage.py`) forbids `proxmoxer`/`aiosqlite` symbols outside the impl files.
- The reconciler is one in-process pure pass (`api/services/reconciler.py::reconcile_once` → `_reap` + `_auto_stop`), spawned by `lifespan` in `api/main.py`. The reaper destroys row-less pool CTs and times-out `creating` rows; auto-stop calls the GUARDED `stopWorkspace(reason="idle")`. It NEVER destroys a `stopped` row.
- Migrations are additive `migrations/NNN_*.sql` applied once via a `schema_migrations` ledger (`api/db/sqliteProvider.py::migrate`). Adding `003_*.sql` is the established, idempotent pattern.
- ttyd already runs PERSISTENT (no `--once`, ADR-0006) and LAN-bound in `cc-worker-config/lxc/worker-template/burrow-boot.sh`. Tab close = detach, not terminate. Destroy is the only kill path.
- Config/secrets live in `api/config.py::Settings` (pydantic-settings, reads gitignored `.env`); the Proxmox token is `proxmox_token_value`, the git-cred stopgap is `git_credential_token` + `mint_repo_credential` (a pluggable seam).

## Standard Architecture (v1.3 target, NEW pieces marked ☆)

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser UI (React 19, ui/src/)                                            │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │
│  │ SetupWizard ☆  │  │ Workspace    │  │ TerminalPanel (xterm)        │   │
│  │ (first-run gate)│  │ List/Layout │  │  + reconnect/restore overlay │   │
│  └───────┬────────┘  └──────┬───────┘  └──────────────┬───────────────┘   │
│          │ /api/v1/setup/*  │ /api/v1/workspaces      │ /ws/.../terminal   │
├──────────┴──────────────────┴─────────────────────────┴───────────────────┤
│  FastAPI control plane (api/)                                              │
│  ┌──────────────┐ ┌─────────────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │ setup ☆      │ │ workspaces / nodes  │ │ internal     │ │ terminal  │  │
│  │ router       │ │ routers             │ │ (bootconfig) │ │ (WS relay)│  │
│  └──────┬───────┘ └─────────┬───────────┘ └──────┬───────┘ └─────┬─────┘  │
│         │                   │                    │               │         │
│  ┌──────┴───────────────────┴────────────────────┴───────────────┴─────┐  │
│  │ WorkspaceService (create/stop/start/destroy saga; persistent-aware ☆)│  │
│  │ SetupService ☆   Reconciler (reap + auto-stop; persistent-safe ☆)    │  │
│  └────────────┬─────────────────────────────────────────┬──────────────┘  │
│               │ ComputeProvider ABC                      │ DbProvider ABC   │
├───────────────┴──────────────────────────────────────────┴────────────────┤
│  Fake / Proxmox compute                            SQLite (003 migration ☆) │
│  + testConnection / verifyTemplate ☆               settings row ☆ +          │
│  (+ suspend/resume ☆ only if Tier 2)               persistent column ☆       │
└────────────────────────────────────────────────────────────────────────────┘
              │ pull-at-boot bootconfig                  ▲ ttyd reattach ☆
              ▼                                          │
   Worker LXC: burrow-boot.sh → tmux session ☆ → ttyd (reattach) → claude
```

### Component Responsibilities (v1.3 delta)

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `SetupService` (`api/services/setupService.py`) | Test Proxmox connection, run preflight permission/template checks, report readiness, read/write the configured-state row | **NEW** |
| `setup` router (`api/routers/setup.py`) | Thin envelope-wrapped surface for the wizard endpoints | **NEW** |
| `SetupWizard` (`ui/src/components/SetupWizard.tsx`) | Multi-step browser flow; gates the app on "configured?" | **NEW** |
| `ComputeProvider` ABC | Gains `testConnection`, `verifyTemplate` (+ optional `suspendCt`/`resumeCt` for Tier 2 persistence) | **MODIFIED** |
| `FakeComputeProvider` | Implements the new capability methods deterministically (CI parity) | **MODIFIED** |
| `ProxmoxComputeProvider` | Real impls of the new capability methods | **MODIFIED** |
| `WorkspaceService` | Persists `persistent` flag at create; (Tier 2) suspend/resume actions | **MODIFIED** |
| `lib/statemachine.py` | New `suspended` state + transitions (Tier 2 only) | **MODIFIED (Tier 2)** |
| `Reconciler` | Proven to never reap a persistent stopped workspace; guards any new "stale stopped" rule | **MODIFIED (tests; code only if a new rule is added)** |
| `migrations/003_*.sql` | `persistent` column on workspaces; singleton `settings` table | **NEW** |
| `burrow-boot.sh` / `provision-template.sh` | Launch ttyd inside a tmux session; reattach on restart; install tmux | **MODIFIED** |

## Feature 1 — Setup Wizard

### New `/api/v1` endpoints

All thin, all under `/api/v1`, all returning the `data`/`meta`/`error` envelope (`lib/envelope.respond`). They delegate to a new `SetupService` so the router stays orchestration-free (mirrors `internal.py`/`nodes.py`).

| Endpoint | Purpose | Backed by |
|----------|---------|-----------|
| `GET /api/v1/setup/status` | "Is Burrow configured yet?" — the gate the UI reads on load | settings row (DB read) |
| `POST /api/v1/setup/test-connection` | Validate a provided Proxmox host + token reaches the API and authenticates | `testConnection()` (**NEW** capability) |
| `POST /api/v1/setup/preflight` | Validate the token's permissions (clone, pool PUT, config PUT — ADR-0003 scope) and that the template VMID exists & is a template | `verifyTemplate()` + a permission probe (**NEW**) |
| `GET /api/v1/setup/health` | Readiness — REUSE the existing `/api/v1/health` (db + compute reachable) | existing `healthcheck()` |
| `POST /api/v1/setup/settings` | UPSERT the validated connection + worker pool/node settings; set `setupCompletedAt` | settings row (DB write) |

Recommendation: do NOT invent a new health endpoint — the existing `GET /api/v1/health` (`api/routers/health.py`) already aggregates `db.healthcheck()` + `compute.healthcheck()` with degrade-not-500; the wizard's health step calls it. `setup/preflight` is the genuinely new check (permissions + template existence), distinct from "reachable".

The wizard does NOT create the PVE least-priv user/role/token — per PROJECT.md that stays operator-run (`cc-worker-config/lxc/host-prime/`). The wizard validates a token the operator pasted and guides the manual `host-prime` steps; it never silently works around them.

### Where "configured?" state lives

**Recommendation: a single-row settings/config table (NEW `003` migration), NOT a derived check.** Rationale:

- A derived check ("any workspaces exist?" / "is `proxmox_token_value` non-empty?") conflates "operator finished the wizard" with incidental state. A token can be in `.env` without the template ever having been verified end-to-end; recording that the validated configuration exists is the wizard's whole point.
- A `settings` row gives an explicit `setupCompletedAt` + the validated non-secret values, queryable through the `DbProvider` seam (Fake-provable, survives restart). Same additive-migration pattern as `002`.

Schema sketch (`003_settings.sql`, singleton row enforced by a fixed PK):

```sql
CREATE TABLE settings (
  id              INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
  setupCompletedAt TEXT,                                -- NULL until the wizard finishes
  proxmoxHost     TEXT,
  templateVmid    INTEGER,
  workerNodes     TEXT DEFAULT '[]',                    -- JSON list
  updatedAt       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
INSERT INTO settings (id) VALUES (1);
```

`GET /api/v1/setup/status` returns `{ configured: setupCompletedAt IS NOT NULL }`. The `DbProvider` ABC gains `getSettings()` / `updateSettings()` (snake_case↔camelCase mapped as elsewhere), implemented in `sqliteProvider.py` and the Postgres stub.

### Secret hygiene — where the Proxmox token is persisted and read

**Recommendation: the token stays in the gitignored `.env` (read via `Settings.proxmox_token_value`); the settings TABLE stores only non-secret connection metadata (host, template VMID, node list, completed-at).** This is the established posture (PROJECT.md: ".env-only; a secrets manager is hosted-path scope") and the ADR-0002 "no secret in the DB / on the worker" lineage.

The friction: the wizard collects the token in the browser. Two honest options, both behind the seam:

- **Option A (recommended for v1):** the wizard validates the token in-memory — POST it to `test-connection`, the service uses it for a one-shot probe, never persists it — then instructs the operator to place it in `.env` and restart; `setup/status` then reads it back via `Settings`. Keeps the "no secret in the DB" rule absolute. Cost: a restart in the flow.
- **Option B:** persist the token in the settings table. Plaintext-in-SQLite on a LAN single-user box is a real posture change and edges into secrets-manager scope. A clear ADR-requiring deviation — defer.

Pick A. It is the smallest change that does not violate the existing secret-hygiene invariants. Flag Option B as the documented future path if the restart friction proves unacceptable at acceptance.

### Staying behind the ComputeProvider seam (CI-provable)

Two NEW capability methods on the ABC, both implemented by Fake AND Proxmox:

```python
# api/compute/provider.py  (MODIFIED — add to ComputeProvider)
@abstractmethod
async def testConnection(self) -> bool: ...                       # reachable + authenticated
@abstractmethod
async def verifyTemplate(self, template_vmid: int) -> bool: ...   # template CT exists & is a template
```

- `FakeComputeProvider.testConnection` returns `True` (or a constructor-injected value for negative-path tests, mirroring the existing `FakeFailures` pattern). `verifyTemplate` returns `True` when `template_vmid == settings.template_vmid`. The entire wizard happy-path AND failure-path is then testable with zero Proxmox.
- `ProxmoxComputeProvider.testConnection` wraps `self._api.version.get()` (already used by `healthcheck`) plus a cheap authenticated read; `verifyTemplate` reads `nodes(node).lxc(vmid).config.get()` and asserts the `template` flag.
- The permission preflight is the one judgment call: a real ACL probe (can I clone? PUT `/pool/burrow-workers`? — ADR-0003) is Proxmox-specific. Keep it behind a single ABC method returning a typed DTO from `models/compute.py` (e.g. `preflight() -> PreflightReport`), so the Fake returns a green report and no `proxmoxer` symbol leaks into the router. The seam-leakage test stays green.

### Idempotency of provision/verify (safe to re-run)

- `test-connection`, `preflight`, `verifyTemplate` are pure reads — inherently idempotent.
- Template PROVISIONING itself (`provision-template.sh`) is operator-run on the host, not over the API (no `pct exec` over HTTPS, ADR-0002). The wizard VERIFIES + GUIDES; it never provisions over the API. The verify is re-runnable.
- `setup/settings` is an UPSERT on the singleton row — re-running overwrites with the same validated values; `setupCompletedAt` is stable once set. Re-running the whole wizard (e.g. token rotation) is safe.

### UI first-run gating

`ui/src/App.tsx` (MODIFIED) currently renders the workspace shell unconditionally (verified). Add a gate:

- NEW hook `ui/src/hooks/useSetupStatus.ts` (TanStack Query, mirrors `useNodes.ts`) → `GET /api/v1/setup/status`.
- In `App.tsx`: while loading, show a splash; if `!configured`, render `<SetupWizard />` instead of the `Navbar`/`WorkspaceList`/`WorkspaceLayout` shell; on completion, invalidate the query and fall through to the shell.
- The wizard's final step ("land the first workspace") reuses the existing `NewWorkspaceModal` create path — no new create flow.

## Feature 2 — Real-Boot v2 Persistence (WSX-02 + WSX-03)

### Does ComputeProvider gain new capabilities?

**WSX-02 (persistent workspaces) does NOT strictly need new compute methods if "persistent" means stop-without-destroy.** `stopCt`/`startCt` already preserve disk (Proxmox `lxc stop`/`start` keeps the rootfs; the tech-spec stop contract is "preserves disk state"). Only destroy frees the CT. So a persistent workspace is fundamentally *a stopped CT the reaper must not destroy* — mostly a flag + reconciler concern, not a new compute capability.

**Recommendation — two tiers; default to the lower one for v1.3 unless acceptance demands snapshots:**

- **Tier 1 (recommended, minimal):** "persistent" = stop/start without destroy + the reaper-survival guarantee. NO new ComputeProvider method, NO new state. Reuses `stopCt`/`startCt` and the existing `stopped` state verbatim. Smallest seam-preserving change; fully Fake-provable.
- **Tier 2 (only if true suspend/resume or snapshot/rollback is required):** add capability methods to the ABC:

  ```python
  async def suspendCt(self, node, vmid) -> ComputeTask: ...   # freeze RAM state
  async def resumeCt(self, node, vmid) -> ComputeTask: ...
  # and/or snapshotCt / rollbackCt
  ```

  Each MUST land in BOTH Fake (model a `suspended` flag on `_FakeContainer`) and Proxmox (`nodes(node).lxc(vmid).status.suspend.post()` / `.resume.post()`, UPID-blocked via `_block`). Adding an ABC method is a documented ADR trigger.

CAVEAT (MEDIUM confidence): LXC suspend/resume relies on kernel CRIU and is historically flaky for UNPRIVILEGED containers (the golden template is unprivileged, tech-spec §9.1). VERIFY at the dev-homelab smoke before committing Tier 2. If suspend is unreliable, snapshot/rollback (disk-level, reliable) or plain stop/start (Tier 1) are the fallbacks. This is exactly why Tier 1 is the default recommendation.

### New state-machine states / transitions

Tier 1 needs NO new state — a persistent workspace uses the existing `stopped` state; the difference is the `persistent` flag the reaper reads. The existing `("running","stop")→"stopped"` and `("stopped","start")→"running"` transitions already do the job.

Tier 2 adds rows to `api/lib/statemachine.py::TRANSITIONS` (MODIFIED):

```python
("running",  "suspend"): "suspended",
("suspended","resume"):  "running",
("suspended","destroy"): "destroyed",   # destroy MUST stay legal from the new state
```

`suspended` becomes a new `WorkspaceStatus` literal (`api/models/workspace.py`, MODIFIED) and a new value in the UI status map (`ui/src/lib/status.ts`).

**Critical (both tiers):** `destroy` MUST be legal from the persistent/new state, or an operator can never reclaim a persistent workspace.

### Persistence as a per-workspace flag at create time

**Yes — a `persistent` boolean chosen at create.** Add `persistent: bool = False` to `WorkspaceCreate` (`api/models/workspace.py`, MODIFIED) and a `persistent` column (`003` migration). Default `False` preserves the ephemeral-by-default principle (tech-spec §2.2). `NewWorkspaceModal.tsx` (MODIFIED) gets a checkbox. The saga persists the flag in `_reserve_vmid_and_row`'s `base` dict (MODIFIED).

### Data-model changes (new columns)

`003_persistence.sql` (NEW) — additive, idempotent under the ledger:

```sql
ALTER TABLE workspaces ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0;
-- Tier 2 only: 'suspended' joins the documented status enum (comment; status is TEXT, no constraint to alter)
```

Plus `_WORKSPACE_COLUMNS` in `sqliteProvider.py` (MODIFIED) gains `persistent`, the `Workspace` DTO gains the field, and the Postgres stub schema (tech-spec §7.2) gets the same column for parity.

### Reconciler / reaper / auto-stop interaction with persistent workspaces

Highest-risk integration point. Three findings, all about `api/services/reconciler.py` (MODIFIED):

1. **Reaper orphan branch (`_reap` case A):** SAFE AS-IS. A row-less pool CT is an orphan regardless of persistence — there is no row to carry the flag. A persistent workspace always has a live row (its VMID is in `live_vmids`), so the existing `if vmid in live_vmids ... continue` guard already protects it. No code change; assert with a test.
2. **Reaper `creating`-timeout branch (`_reap` case B):** UNCHANGED — persistence has no bearing on a stuck `creating` row.
3. **Idle auto-stop (`_auto_stop`):** the only real interaction, and it is SUBTLE. Auto-stop SHOULD still stop an idle RUNNING persistent workspace — stop preserves state, so auto-stop and persistence are complementary, not conflicting. So `_auto_stop` does NOT skip persistent running workspaces.

   The "must not reap a persistent STOPPED workspace" requirement is ALREADY satisfied: the current reaper NEVER destroys a `stopped`-with-a-live-row workspace (it only destroys row-less orphans and times-out `creating` rows). The integration work is therefore: **add a regression test asserting a persistent (and an ephemeral) stopped workspace survives a reconcile pass, and document that any FUTURE "reap stale stopped" rule MUST exclude `persistent=True`.**

   IF v1.3 adds a "destroy ephemeral workspaces stopped longer than N" reaper rule (a plausible companion to persistence), THAT new rule must read `row.persistent` and skip persistent rows — the ONLY place the flag changes reaper behavior. Decide this explicitly (see Gaps).

### Scrollback restore — end-to-end flow (WSX-03)

```
worker boot (burrow-boot.sh, MODIFIED)
  └─ start/attach a named tmux session  ── NEW (tmux new-session -A -s burrow ...)
        └─ ttyd attaches to THAT session (not `bash -lc "exec claude"` directly)  ── MODIFIED exec line
              │  scrollback lives in the multiplexer, survives ttyd client churn AND a stop/start
              ▼
control plane (terminal.py, UNCHANGED — opaque relay)
  └─ /ws/workspaces/{id}/terminal bridges browser ↔ ttyd verbatim (SC-7 frame-type preserved)
        ▼
browser (TerminalPanel.tsx + useTerminal.ts; reconnect overlay UNCHANGED, verify)
  └─ on reconnect, ttyd replays the multiplexer's scrollback buffer
        ▲
  server-truth poll (useWorkspaces.ts, UNCHANGED): the ~3s status poll + onTerminalEvent
  invalidate already drives "is it running?"; reattach proceeds only when status==running
  (the terminal router's access gate enforces it).
```

Key design points:

- The multiplexer is the source of scrollback truth, NOT the control plane. Keep `terminal.py` a dumb opaque bridge (SC-7). Do NOT add server-side scrollback buffering — it breaks frame-type preservation and adds state the seam design avoids.
- `burrow-boot.sh` change is surgical: replace the final `exec ttyd ... bash -lc "cd '${START_DIR}' && exec ${CLAUDE_CMD}"` with an invocation that wraps the command in `tmux new-session -A -s burrow ...` (`-A` = attach-if-exists, create-otherwise → idempotent reattach across stop/start). This COMPOSES with ADR-0006 (persistent ttyd): now BOTH ttyd AND the session survive, so on a worker restart (start after stop) the boot script reattaches the same tmux session and scrollback survives the stop/start cycle, not just tab-close.
- Hermetic test home exists: the boot-harness tests (`api/tests/boot/test_burrow_boot.py`) prove boot-script behavior with no real infra. Add a case asserting the `tmux new-session -A` invocation is present. Real reattach is a homelab-smoke line.
- Choose tmux over zellij for v1.3: tmux is in Ubuntu base repos (one `apt-get install` line in `provision-template.sh`, MODIFIED), battle-tested for detach/reattach, and `new-session -A` gives idempotent reattach in one flag. zellij is heavier and faster-moving. KISS → tmux.

## Feature 3 — First Real-Infra Acceptance (ACC-01/02/03)

Mostly NO new code (PROJECT.md). Human UAT against real Proxmox + GHCR:

- **ACC-01:** real create→terminal→stop→start→destroy + reaper/auto-stop/capacity on real CTs, real multi-node `selectNode`. Exercises the EXISTING saga/reconciler/selection against real Proxmox. Code impact: only fixes the smoke surfaces (the `[ASSUMED]` hostname→VMID parse in `burrow-boot.sh`, the `mint_repo_credential` A3 issuer stopgap, suspend reliability if Tier 2). Capture as `*-HUMAN-UAT.md` items.
- **ACC-02:** first live release-please PR + harden-runner `egress-policy: block` flip + real GHCR publish + cosign/attestation verify. CI/CD only; no `api/` code.
- **ACC-03:** the per-phase `*-HUMAN-UAT.md` checklists flipped to passed.

Acceptance depends on the wizard (to get a real connection configured) and persistence (to exercise stop/start with state), so it sequences LAST.

## Architectural Patterns (reused, not invented)

### Pattern 1: New capability on the ComputeProvider ABC, with Fake parity
**What:** every new compute behavior (testConnection, verifyTemplate, optional suspend/resume) is an `@abstractmethod` on `ComputeProvider`, implemented by BOTH `FakeComputeProvider` (deterministic, injectable failures) and `ProxmoxComputeProvider` (UPID-blocked via `_block`).
**When:** any time the wizard or persistence needs a real Proxmox operation.
**Trade-offs:** extending the (deliberately frozen) contract is an ADR-worthy change — but it is the ONLY way to keep services seam-pure and CI-provable. The Fake masks real-infra failure modes (e.g. CRIU suspend), so each new method needs a homelab-smoke acceptance line.

### Pattern 2: Additive `003` migration under the ledger
**What:** all schema change is a new `migrations/003_*.sql`, applied once by `schema_migrations`. Never edit `001`/`002`.
**When:** the `persistent` column and the `settings` table.
**Trade-offs:** SQLite `ALTER TABLE ADD COLUMN` is cheap and online; `DEFAULT 0` needs no backfill.

### Pattern 3: Thin router → service, envelope-wrapped
**What:** the `setup` router validates, calls `SetupService`, and `respond(...)`s — exactly like `internal.py`/`nodes.py`. No orchestration or driver symbol in the router.
**When:** all five setup endpoints.

### Pattern 4: State change is a TRANSITIONS-table edit
**What:** any new lifecycle state (Tier-2 `suspended`) is rows added to `lib/statemachine.py::TRANSITIONS`; `assert_transition` enforces it centrally, so services/routers need no new branching.

## Data Flow — the two changed flows

### Setup / first-run
```
UI load → useSetupStatus → GET /api/v1/setup/status → SetupService.isConfigured (settings row)
   ↓ not configured
SetupWizard → POST test-connection → ComputeProvider.testConnection (Fake:True / Proxmox:version+auth)
   → POST preflight → verifyTemplate + permission probe
   → GET health (existing) → POST settings (UPSERT singleton, set setupCompletedAt)
   → invalidate useSetupStatus → app shell renders → NewWorkspaceModal (first workspace)
```

### Persistence + scrollback restore
```
create(persistent=true) → _reserve_vmid_and_row persists `persistent` → saga otherwise unchanged
stop  → stopWorkspace → assert_transition(running,stop) → compute.stopCt (disk preserved)
start → startWorkspace → compute.startCt → burrow-boot.sh tmux new-session -A (reattach) → ttyd
   → _wait_ttyd → running → terminal relay reconnects → ttyd replays tmux scrollback
reconcile pass: reaper skips (live row) ; auto-stop may stop an idle RUNNING persistent ws (OK)
```

## Anti-Patterns to avoid

### Anti-Pattern 1: Server-side scrollback buffering in the relay
**What people do:** add a ring buffer in `terminal.py` to replay history on reconnect.
**Why it's wrong:** breaks the SC-7 opaque-relay invariant (frame-type preservation), adds per-workspace server state the seam design avoids, and duplicates what the multiplexer already does.
**Do this instead:** scrollback lives in tmux on the worker (WSX-03 as specified). The relay stays dumb.

### Anti-Pattern 2: Persisting the Proxmox token in the DB to "complete" the wizard
**What people do:** store the pasted token in the settings table so the API can use it without a restart.
**Why it's wrong:** violates the `.env`-only secret posture (PROJECT.md, ADR-0002 lineage) and edges into secrets-manager scope (out of v1).
**Do this instead:** validate in-memory, write the token to `.env`, restart (Option A). If unacceptable, that is a documented ADR and likely a milestone boundary.

### Anti-Pattern 3: A derived "is it configured?" heuristic
**What people do:** infer setup completion from "token present" or "≥1 workspace exists".
**Why it's wrong:** conflates incidental state with operator intent; fragile across token rotation and workspace deletion.
**Do this instead:** an explicit `setupCompletedAt` on the singleton settings row.

### Anti-Pattern 4: Making the reaper "persistence-aware" where it is already safe
**What people do:** add `if row.persistent: continue` to the orphan or `creating`-timeout branch.
**Why it's wrong:** the orphan branch operates on row-LESS CTs (no flag exists); the `creating`-timeout branch is unrelated to persistence. Such guards are dead code implying protection the branch never threatened.
**Do this instead:** add the survival regression test; guard ONLY a NEW "reap stale stopped ephemerals" rule, if one is added.

## Suggested Build Order (dependency-respecting)

Phase numbering continues from v1.2 (last phase 9) → v1.3 resumes at 10.

1. **Phase 10 — Persistence data model + state machine (foundation).**
   - `003_persistence.sql` (NEW: `persistent` column), `Workspace`/`WorkspaceCreate` field (MODIFIED), `_WORKSPACE_COLUMNS` (MODIFIED), `_reserve_vmid_and_row` persists the flag (MODIFIED).
   - Tier decision: stop/start (Tier 1, no ABC change) vs suspend/resume (Tier 2, ABC + statemachine change). Recommend Tier 1 unless acceptance demands snapshots.
   - Reconciler regression tests: persistent + ephemeral stopped workspaces survive a reconcile pass (MODIFIED tests; reconciler code UNCHANGED for Tier 1).
   - Touches: `migrations/`, `models/workspace.py`, `services/workspaceService.py`, `services/reconciler.py` (tests), `lib/statemachine.py` (Tier 2 only). CI-provable over Fake. **Build first** — the flag underpins later phases.

2. **Phase 11 — Scrollback restore (WSX-03, worker-side).**
   - `burrow-boot.sh` tmux `new-session -A` (MODIFIED), `provision-template.sh` installs tmux (MODIFIED), boot-harness test asserts the invocation (MODIFIED tests).
   - UI: confirm `TerminalPanel`/reconnect overlay reattaches cleanly (likely UNCHANGED; verify).
   - Code-independent of Phase 10 but conceptually pairs with it. Buildable/CI-provable via the boot harness; real reattach is a homelab-smoke line. Can parallelize with Phase 12.

3. **Phase 12 — Setup wizard backend (SetupService + endpoints + capability methods).**
   - `ComputeProvider` gains `testConnection`/`verifyTemplate` (+ preflight) (MODIFIED ABC), Fake + Proxmox impls (MODIFIED), `setupService.py` (NEW), `routers/setup.py` (NEW), `DbProvider.getSettings/updateSettings` (MODIFIED) over the `003` settings table, `main.py` router include + `get_setup_service` DI (MODIFIED).
   - Fully CI-provable over Fake (happy + failure paths).

4. **Phase 13 — Setup wizard UI + first-run gate.**
   - `useSetupStatus.ts` (NEW), `SetupWizard.tsx` (NEW), `App.tsx` gate (MODIFIED), `NewWorkspaceModal` persistent checkbox (MODIFIED). Wizard's final step reuses the create path. vitest + Playwright over Fake.

5. **Phase 14 — First real-infra acceptance (ACC-01/02/03) + 07r e2e nit.**
   - Human UAT against real Proxmox + GHCR; flips the ★ items and `*-HUMAN-UAT.md` checklists. Code only as smoke-surfaced fixes (hostname→VMID parse, A3 credential issuer, suspend reliability if Tier 2). The 07r stop/start e2e cleanup robustness ride-along lands here.
   - **Build last** — depends on a configurable connection (wizard) and stop/start state (persistence).

Rationale: the data model is the shared foundation; the worker-side scrollback change is independent and low-risk so it can parallelize with the wizard backend; wizard backend precedes wizard UI (UI consumes the endpoints); acceptance is last because it exercises everything end-to-end on real hardware.

## ADR triggers (Burrow requires an ADR for any baseline deviation)

Match the existing Nygard style (Status / Context / Decision / Consequences / Revisit trigger), HTML-comment SPDX header line 1, numbered `ADR-0011+`.

| Likely ADR | Trigger | Why it deviates from baseline |
|------------|---------|-------------------------------|
| **ADR-0011 — Setup-state / config store + first-run gate** | NEW singleton `settings` table + a "configured?" control-flow + new DbProvider methods | Introduces a new persisted store and a first-run flow that did not exist; extends the DbProvider contract. |
| **ADR-0012 — New ComputeProvider capabilities (testConnection / verifyTemplate / preflight)** | New `@abstractmethod`s on the ABC | The ComputeProvider contract is frozen-by-design (provider.py docstring); extending it is a deliberate seam change requiring Fake+Proxmox parity. |
| **ADR-0013 — Persistence model: per-workspace `persistent` flag + stop/start (Tier 1) OR suspend/resume state (Tier 2)** | `persistent` column + (Tier 2) a new `suspended` state and ABC suspend/resume methods; the reaper-exclusion rule | Adds a lifecycle dimension and (Tier 2) a new state + new compute capabilities; records the reaper-survival guarantee. |
| **ADR-0014 — Worker scrollback via tmux multiplexer** | `burrow-boot.sh` launches ttyd inside tmux; tmux added to the golden template | Changes the worker boot contract and adds a runtime dependency; COMPOSES with (does not replace) ADR-0006. |
| **(only if Option B chosen) — Proxmox token at rest in the DB** | persisting the token in SQLite | Direct deviation from `.env`-only secrets; arguably out-of-scope (secrets manager). Prefer Option A and skip this ADR. |

Minimum ADR set if Tier 1 + Option A is chosen: ADR-0011, ADR-0012, ADR-0013, ADR-0014. The token-at-rest ADR is avoided by design.

## Integration Points (named, new-vs-modified)

### Internal boundaries touched

| Boundary | File | Change |
|----------|------|--------|
| Setup endpoints ↔ service | `api/routers/setup.py`, `api/services/setupService.py` | **NEW** both |
| Service ↔ compute (connection/template/preflight) | `api/compute/provider.py` + `fakeProvider.py` + `proxmoxProvider.py` | **MODIFIED** (new methods, Fake+Proxmox parity) |
| Service ↔ settings persistence | `api/db/provider.py`, `api/db/sqliteProvider.py`, `api/db/postgresProvider.py` | **MODIFIED** (`getSettings`/`updateSettings`) |
| Schema | `api/db/migrations/003_*.sql` | **NEW** |
| Workspace model | `api/models/workspace.py` | **MODIFIED** (`persistent`; Tier-2 `suspended` literal) |
| Create saga | `api/services/workspaceService.py` (`_reserve_vmid_and_row`, `createWorkspace`) | **MODIFIED** (persist flag; Tier-2 suspend/resume actions) |
| State machine | `api/lib/statemachine.py::TRANSITIONS` | **MODIFIED (Tier 2 only)** |
| Reconciler | `api/services/reconciler.py` | **MODIFIED** (survival tests; new code only if a "reap stale stopped" rule is added) |
| App wiring / DI | `api/main.py` (`get_setup_service`, router include) | **MODIFIED** |
| Worker boot | `cc-worker-config/lxc/worker-template/burrow-boot.sh`, `provision-template.sh` | **MODIFIED** |
| First-run gate | `ui/src/App.tsx`, `ui/src/hooks/useSetupStatus.ts`, `ui/src/components/SetupWizard.tsx` | `App.tsx` **MODIFIED**; hooks/component **NEW** |
| Create-with-persistence UI | `ui/src/components/NewWorkspaceModal.tsx`, `ui/src/lib/status.ts`, `ui/src/types/workspace.ts` | **MODIFIED** |

### External services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| Proxmox VE | Behind `ProxmoxComputeProvider` only (proxmoxer, UPID-blocked) | New testConnection/verifyTemplate/[suspend] here; CA-pinned TLS unchanged; CRIU suspend reliability is the homelab-smoke unknown. |
| GHCR + release-please + cosign | CI/CD only (ACC-02) | No `api/` code; egress-policy block flip + first live release PR. |
| cc-worker-config repo | pulled at boot (ADR-0002) | tmux session added in `burrow-boot.sh`; manifest/CLAUDE.md flow unchanged. |

## Scaling Considerations

Out of scope for v1.3 (LAN single-operator, `--workers 1` per ADR-0010). Persistence raises ONE finite-resource consideration: persistent stopped workspaces hold a VMID and disk indefinitely (by design — destroy is the reclamation action). The node-RAM capacity guard bounds RUNNING concurrency; persistent STOPPED workspaces consume disk + a VMID-pool slot, so the worker pool range (`worker_pool_start..end`, default 200-299 = 100 slots) is the real ceiling. If persistent workspaces accumulate, pool exhaustion surfaces as `NoFreeVmidError` at create — acceptable and visible for a single operator; revisit the pool size, not the architecture.

## Confidence & Gaps

- **HIGH** on the wizard integration shape, the settings-table recommendation, the seam-method + Fake-parity pattern, the reaper-already-safe finding, the tmux scrollback flow, and the build order — all grounded directly in the read source.
- **MEDIUM** on Tier-2 suspend/resume viability: CRIU suspend for unprivileged LXC is the documented risk; the recommendation defaults to Tier 1 (stop/start) to avoid betting on it. Resolve at the dev-homelab smoke before committing to a `suspended` state.
- **GAP for the roadmapper to flag:** whether v1.3 adds a "reap stale stopped EPHEMERAL workspaces" reaper rule. If yes, that is the concrete consumer of `persistent` in the reaper and needs its own design line; if no, the flag only gates the create UI + future cleanup, and the reaper change is just a regression test. A product decision, not a research one.
- **GAP:** the `mint_repo_credential` A3 real-issuer and the `[ASSUMED]` hostname→VMID parse in `burrow-boot.sh` are pre-existing stopgaps that ACC-01 will stress on real infra — surface them as acceptance-phase risks, not new v1.3 design.

## Sources

- Repo source (authoritative, read directly): `api/services/workspaceService.py`, `api/services/reconciler.py`, `api/compute/provider.py`, `api/compute/fakeProvider.py`, `api/compute/proxmoxProvider.py`, `api/lib/statemachine.py`, `api/config.py`, `api/main.py`, `api/routers/{health,internal,nodes,terminal}.py`, `api/db/{provider,sqliteProvider}.py`, `api/db/migrations/00{1,2}_*.sql`, `api/models/workspace.py`, `cc-worker-config/lxc/worker-template/burrow-boot.sh`, `ui/src/App.tsx`.
- Decisions (authoritative): `docs/adr/ADR-0001..0010` (esp. ADR-0002 pull-at-boot/secret hygiene, ADR-0006 persistent ttyd, ADR-0010 reconciler + capacity lock), `.planning/PROJECT.md`, `docs/tech-spec.md`.

---
*Architecture research for: Burrow v1.3 "Go Live" — setup wizard, persistence (WSX-02/03), real-infra acceptance*
*Researched: 2026-06-24*
