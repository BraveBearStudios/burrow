<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 3: Reproducible Workers - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

A booted worker pulls its CLAUDE.md and a versioned plugin set fresh from
`cc-worker-config` so workspaces are reproducible and plugin drift is impossible,
with no credentials left behind. This phase replaces the Phase-0 stub in
`cc-worker-config/lxc/worker-template/burrow-boot.sh` with the live pull-at-boot
flow against the Phase-1 `GET /api/v1/internal/bootconfig/{vmid}` endpoint, defines
and validates the plugin manifest (`cc-worker-config/plugins/manifest.json`), and
proves credential hygiene (no token in `/etc/burrow/worker.env`; no repo URL or
credential in event-log `data` or structured logs).

In scope: the boot script's live fetch/clone/launch path, VMID self-resolution,
the manifest schema + bake-vs-pull split, ERR-trapped boot-failure surfacing, the
B4 cadence ADR, and the tests that cover all of the above. Out of scope: real
Proxmox boot validation (dev-homelab smoke gate only — CI can only lint/unit-test
the boot script and manifest schema), and any change to the Phase-1 bootconfig
endpoint contract (frozen).

</domain>

<decisions>
## Implementation Decisions

### Plugin Cadence & Reproducibility (B4)
- Cadence is **boot-time-latest**: the boot pulls the `cc-worker-config` branch HEAD
  on each boot (tech-spec §988). Reproducibility is delivered by manifest ref-pinning,
  not by snapshotting the config repo per workspace.
- The manifest pins each `claude-plugin` entry to an **immutable ref** (git tag/commit
  SHA), so two boots of the same manifest produce an identical plugin set (SC-2).
- Plugin-type split: `binary` and `npm-global` types are **baked into the golden
  template** (provision-time); only `claude-plugin` types are **pulled fresh at boot**
  (SC-2).
- The B4 decision is recorded as a new **ADR-0009 (plugin cadence: boot-time-latest)**
  so reproducibility semantics are explicit (SC-4). The ADR notes the snapshot-at-create
  alternative and the revisit trigger (per-workspace pinning when the manifest stabilizes).

### Manifest Format & Schema
- Format and location: **`cc-worker-config/plugins/manifest.json`** — JSON, per
  tech-spec §11.1 ("Pinned plugin sources + refs").
- Entry schema: each plugin is `{ name, type: claude-plugin|binary|npm-global, source,
  ref }`; `type` drives the bake-vs-pull decision above.
- Validation: the manifest is **JSON-Schema validated at boot** — a malformed manifest
  fails the boot (non-zero, ERR-trapped) rather than silently degrading. A schema unit
  test lives in-repo so manifest drift is caught in CI.
- An unknown / unsupported plugin `type` at boot **fails the boot**.

### Boot Error Handling & Credential Hygiene
- Boot-failure surfacing reuses the existing Phase-1 path: the script keeps
  `set -euo pipefail` and adds an **ERR trap** that logs a redacted line and exits
  non-zero. The control-plane create saga's ttyd-health timeout then records the typed
  `boot.error` event. **No new worker→control-plane endpoint** is added (avoids a new
  internal threat surface; YAGNI).
- The bootconfig GET is **bounded-retry** (≈5 attempts, capped backoff) before the
  script gives up and fails — so a transient control-plane blip does not abort a boot.
- The short-lived, repo-scoped git credential is fed to `git clone` via an **in-memory
  `GIT_ASKPASS` / credential helper inside a subshell** — never written to disk, never
  to `/etc/burrow/worker.env`, and unset after the clone (SC-3). The token is never
  embedded in a clone URL (which would leak it via `ps`, the reflog, and remote config).
- A **scrub-proof test** (shell or Python harness) asserts no token remains in
  `worker.env` post-boot and that the repo URL / credential never appears in any logged
  line or event payload (SC-3).

### Claude's Discretion
- Exact retry counts/backoff curve, the VMID-from-hostname resolution mechanics, the
  precise test harness (bats/shunit2 vs a Python subprocess harness), and ADR prose are
  at Claude's discretion within the decisions above.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cc-worker-config/lxc/worker-template/burrow-boot.sh` — Phase-0 stub with the frozen
  ttyd contract (persistent, no `--once`, `--interface 0.0.0.0`; SC-8/SC-9, ADR-0006/0007)
  and a documented pull-at-boot stub to replace.
- `api/routers/internal.py` — the live `GET /api/v1/internal/bootconfig/{vmid}` endpoint:
  returns `configRepo`, `configBranch`, `projectRepo`, `projectBranch`, `gitCredential`
  (camelCase envelope). vmid-in-pool gate + per-fetch minted credential already implemented.
- `cc-worker-config/lxc/worker-template/provision-template.sh` — golden-template build
  (the bake target for `binary`/`npm-global` plugins).
- `cc-worker-config/systemd/burrow-worker.service` — the unit that runs `burrow-boot.sh`
  (Restart policy + optional EnvironmentFile).

### Established Patterns
- Secret redaction precedent: Phase-1 create saga logs `boot.error` with `_safe(exc)`
  redaction; no credential / repo-token in event `data` (T-01-09, Pitfall 7/13).
- camelCase JSON ↔ snake_case via Pydantic `CamelModel` alias generator.
- ADR convention: `docs/adr/ADR-000N-*.md` with Status/Context/Decision/Consequences/
  Revisit-trigger sections (see ADR-0002).

### Integration Points
- Boot script ↔ `GET /api/v1/internal/bootconfig/{vmid}` (consumes the Phase-1 contract).
- Manifest ↔ `Template.plugin_manifest` model (tech-spec §11.1; stored as TEXT JSON).
- Boot failure ↔ create-saga ttyd-health timeout → `boot.error` event (Phase-1 path).

</code_context>

<specifics>
## Specific Ideas

- tech-spec §11.1 (`plugins/manifest.json`) and §988 (cadence recommendation) are the
  authoritative references for format and cadence.
- ADR-0002 (pull-at-boot) freezes the fetch contract this phase implements; ADR-0009
  (new) records the B4 cadence decision.

</specifics>

<deferred>
## Deferred Ideas

- Per-workspace plugin version pinning / snapshot-at-create cadence — deferred until the
  manifest stabilizes (noted as the ADR-0009 revisit trigger).
- A dedicated worker→control-plane boot-status POST endpoint — deferred; the saga
  health-timeout path covers `boot.error` surfacing for v1.

</deferred>
