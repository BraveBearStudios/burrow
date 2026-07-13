<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0018: Multi-agent worker design contract (research spike)

## Status

Accepted (research-only). Records a design contract and an additivity finding; ships
NO product code. The build (agent registry, per-agent secrets, create-modal picker,
launch selection) is AGENT-03 and later, a future milestone deferred out of v1.4.

## Context

A Burrow worker today boots exactly one agent: Claude Code. `burrow-boot.sh` hardcodes
the launch command (`CLAUDE_CMD="claude"`, or `rtk claude` when present) and execs it
inside a single fixed tmux session under ttyd:
`exec ttyd ... bash -lc "cd '${START_DIR}' && exec tmux new-session -A -s burrow ${CLAUDE_CMD}"`.
The one credential a worker needs (a GitHub token for the config and project clones) is
resolved server-side by `mint_repo_credential` (delegating to `CredentialResolver`),
delivered pull-at-boot in the non-secret bootconfig envelope as `.data.gitCredential`
(ADR-0002), consumed once by an in-memory `GIT_ASKPASS` helper, and discarded. No secret
is ever written to `/etc/burrow/worker.env` or to disk.

AGENT-02 asks a narrow, forward-looking question: can the v1.4 credential seam landed in
ADR-0015 (the encrypted `settings` store + `CredentialResolver` + the pull-at-boot
manifest and bootconfig) support running other terminal coding agents (Cursor CLI, GitHub
Copilot CLI, OpenAI Codex CLI) in a worker later, WITHOUT reworking the store, the
`DbProvider` abstraction, the Fernet/key-provider crypto, the admin gate, or the boot
contract? This ADR answers that with evidence. It does NOT design the full per-agent auth
system; that is AGENT-03 and later.

## Findings: how each CLI runs headless in a container, and its auth model

Each of the three CLIs offers a non-interactive mode and an environment-variable secret
path suitable for an unattended Linux container. Each also offers an interactive OAuth or
browser login that is NOT container-friendly. The container-viable path for all three is
the same shape: one opaque secret supplied via an environment variable at launch.

| Agent CLI | Headless / non-interactive | Auth model (container path) | Credential shape | Env var | Blocker / caveat |
|---|---|---|---|---|---|
| Cursor CLI (`cursor-agent`, alias `agent`) | Yes. Print mode `agent -p "..."` with `--output-format text\|json\|stream-json`; designed for CI and scripts. | API key env var for headless; `cursor-agent login` is an interactive browser flow. | Opaque Cursor account API key. | `CURSOR_API_KEY` | Community bug reports of `-p` mode hanging / not releasing the terminal (UNVERIFIED; must be smoke-tested under ttyd/tmux before adoption). |
| GitHub Copilot CLI (`@github/copilot`, command `copilot`) | Yes. Programmatic mode `copilot -p "PROMPT"` runs non-interactively and exits. | Env var token; interactive `/login` otherwise. | Fine-grained GitHub PAT with the "Copilot Requests" account permission, tied to a personal account; requires an active Copilot subscription. | `COPILOT_GITHUB_TOKEN` (preferred), then `GH_TOKEN`, then `GITHUB_TOKEN` | Distinct from the legacy `gh copilot` extension (suggest/explain only, `gh auth login`). Target the standalone agent. The credential is a GitHub PAT, the SAME kind Burrow already stores, but a separately scoped token. |
| OpenAI Codex CLI (`@openai/codex`, command `codex`) | Yes. `codex exec "..."` runs non-interactively; `--json`, `--ephemeral`, `--sandbox` for CI. | API key env var, or `codex login --api-key`; ChatGPT sign-in is an interactive browser OAuth. | OpenAI API key (`sk-...`), or a ChatGPT-plan access token. | `OPENAI_API_KEY` (also `CODEX_API_KEY` inline in some flows) | ChatGPT OAuth sign-in opens a browser and is not headless; device-code sign-in for headless hosts can be gated by a workspace admin (issue-reported, ASSUMED). API-key path is the container path. Codex caches auth to `~/.codex/auth.json` in plaintext, so treat the home dir as sensitive. |

Common shape across all three: install as a `binary` (Cursor's installer) or an
`npm-global` package (`@github/copilot`, `@openai/codex`), then launch a print/exec
subcommand with one secret read from an environment variable. This is exactly the shape
Burrow's existing seams already accommodate.

## Design contract: mapping each agent onto the existing seams

### Install: the plugin manifest already covers it

The manifest schema (`cc-worker-config/plugins/manifest.schema.json`) accepts
`type ∈ {claude-plugin, binary, npm-global}`. Cursor installs as a `binary`; Copilot and
Codex install as `npm-global`. All three therefore fit the EXISTING manifest types and get
baked into the golden template at provision time (binary and npm-global entries are baked,
not pulled at boot). Installing a new agent needs no schema change. A future `agent` type
or a per-agent launch descriptor is OPTIONAL sugar, not a requirement.

### Launch: replace the hardcoded command with a selector

The only hardcoded coupling to Claude is the `CLAUDE_CMD="claude"` line and the final
`exec`. AGENT-03 replaces that constant with a selector driven by a NEW non-secret
bootconfig field (e.g. `.data.agent ∈ {claude, cursor, copilot, codex}`), resolved from a
future `WorkspaceCreate.agent` field and a create-modal picker (default `claude`, so
existing workers are unchanged). The bootconfig endpoint already delivers non-secret intent
pull-at-boot (ADR-0002); `agent` is one more non-secret field alongside `configRepo` and
`projectRepo`. ttyd and the single `burrow` tmux session are unchanged: one agent per
worker, chosen at create.

### Secret: extend the keyed store, mint like `gitCredential`

The credential store is already keyed by a string. `DbProvider.getCredentialCiphertext(key)`
takes `key ∈ {"proxmox_token", "git_token"}` and maps it to a column via
`_CIPHERTEXT_COLUMNS`. A per-agent secret is just a new key. The additive extension points,
none of which change an existing signature:

1. **Store columns or a table.** Add nullable ciphertext + last4 columns to the singleton
   `settings` table via a NEW migration (`005`), exactly as `004` added `git_token_enc` /
   `proxmox_token_enc`. For an open-ended set of agents, a dedicated `agent_credentials`
   table keyed by agent id (one row per agent) is the cleaner shape and stays behind
   `DbProvider`. Either is purely additive.
2. **Provider maps.** Extend `_CIPHERTEXT_COLUMNS` and `_CREDENTIAL_COLUMNS` in
   `SqliteProvider` (or add the new table's accessors). `getCredentialCiphertext(key)` and
   `setCredentials(updates)` keep their signatures; only the set of valid keys grows.
3. **Resolver method.** Add `CredentialResolver.agent_secret(agent_id)`, mirroring
   `git_credential` / `proxmox_token`: store-first, `.env` fallback, decrypt through the
   SAME `SecretBox` / Fernet / `SecretKeyProvider`. No new crypto and no new key: it reuses
   `BURROW_SECRET_KEY` and the `KmsSecretKeyProvider` seam reserved for the hosted path.
4. **Admin gate + audit for free.** The `require_admin` argon2id gate and the append-only
   `audit_log` already protect "the credential surface". A new per-agent write endpoint
   rides the same gate and audit trail with no new access-control code.
5. **Delivery.** Mint the agent secret the way `gitCredential` is minted today: resolved
   server-side, delivered in the bootconfig `.data`, read into a shell-local in
   `burrow-boot.sh`, and exported as the agent's expected env var (`CURSOR_API_KEY`,
   `COPILOT_GITHUB_TOKEN`, or `OPENAI_API_KEY`) immediately before the `exec` launch line.
   This reuses the existing credential-hygiene pattern (subshell-local, never on disk,
   redaction backstop). One honest variation: the git credential is unset BEFORE launch,
   whereas an agent key must persist into the launched process environment, so it is placed
   in the launch command's environment rather than unset. It is still never written to
   `worker.env` or disk.

## Decision

The v1.4 ADR-0015 credential seam IS additive for future per-agent authentication. Adding
Cursor, Copilot, or Codex support requires NO rewrite of the `DbProvider` abstract base,
the `SecretBox` / Fernet / `SecretKeyProvider` crypto, the admin gate, or the audit log.
The seam was built keyed by a string and behind abstractions, so it is open for extension
and closed for modification.

The evidence: `getCredentialCiphertext(key: str)` is already parameterised by credential
key; a per-agent credential is a new key value plus a new column set (or an
`agent_credentials` table) reached through the unchanged seam. The three surfaces AGENT-03
must ADD, all additive, are:

- a new store key and its column(s) or table (migration `005`), plus a
  `CredentialResolver.agent_secret` method and an admin-gated write endpoint;
- a non-secret `agent` field on `WorkspaceCreate`, the bootconfig envelope, and the
  create-modal, driving a launch-command selector in `burrow-boot.sh`;
- the minted per-agent secret as a new `.data` field on the internal bootconfig, exported
  as the agent's env var just before `exec`.

No existing signature or stored-column meaning changes. This is the additive verdict the
phase asked to confirm.

## Consequences

**Positive:**

- AGENT-03 is a bounded, additive build: extend a keyed store, add a resolver method, add a
  non-secret selector field, and swap one hardcoded launch constant for a lookup.
- Per-agent secrets inherit encryption at rest, the write-only status model, the admin
  gate, and the audit trail from ADR-0015 with no new security machinery.
- The `DbProvider` and `SecretKeyProvider` seams keep the hosted path (Postgres, Key Vault,
  KMS) additive for per-agent secrets too, not just the two v1 credentials.

**Negative / trade-offs:**

- A per-agent secret, like `mint_repo_credential` today, would be a single global value per
  agent, not per-user, until the hosted Entra path arrives.
- Each supported agent adds a distinct credential the operator must supply and rotate, and a
  distinct golden-template install to maintain and scan.
- The write-only API-key store fits an env-var secret cleanly. An agent whose ONLY viable
  auth is an interactive OAuth or refreshable device-flow token pair would not fit the store
  as-is and would need a token-refresh story (see open questions).

**Neutral / follow-on:**

- The boot-harness scrub-proof test (`api/tests/boot/`) extends to assert the new secret
  never leaks, exactly as it does for `gitCredential`.
- Running more than one agent concurrently in a single worker would reopen the fixed
  single-`burrow`-tmux-session contract (ADR-0014's own revisit trigger). This contract
  keeps v1 multi-agent to one agent per worker, which needs no tmux change.

## Open questions

1. OAuth-only agents. All three v1 targets expose an API-key or PAT env-var path, so the
   write-only store covers them. A future agent that is OAuth-device-flow-only would need a
   refreshable-token design the current write-only store does not model (UNVERIFIED whether
   any target agent will force this).
2. Cursor `-p` termination under ttyd/tmux. Forum reports of print mode hanging must be
   smoke-tested on the homelab before Cursor is adopted (UNVERIFIED).
3. Copilot subscription and PAT scoping. The "Copilot Requests" fine-grained PAT is tied to
   a personal account and needs an active subscription; the operator-supply and rotation UX
   for that is an AGENT-03 product question.
4. Codex plaintext `~/.codex/auth.json`. If Codex writes auth to the home dir even when fed
   an env var, the worker home must be treated as sensitive and cleaned at destroy
   (UNVERIFIED behaviour when `OPENAI_API_KEY` is set).

## Recommended AGENT-03+ build order

1. Agent registry: a static config (agent id, install manifest entry or type, launch-command
   template, required env-var name, credential store key), read by both the API and the boot
   selector. Single source of truth.
2. Store extension: migration `005` (or the `agent_credentials` table) + the
   `_CIPHERTEXT_COLUMNS` / provider entries + `CredentialResolver.agent_secret` + an
   admin-gated write endpoint reusing the ADR-0015 surface and audit log.
3. `WorkspaceCreate.agent` DTO field + the create-modal picker (default `claude`,
   backward-compatible).
4. Bootconfig envelope: add the non-secret `agent` field and the minted per-agent secret;
   add the launch selector and the env-var export before `exec` in `burrow-boot.sh`.
5. Golden-template bake: add the chosen agent CLIs as `binary` / `npm-global` manifest
   entries; extend Trivy/scan coverage.
6. Tests and smoke: extend the boot-harness scrub-proof test to the new secret; run a
   per-agent lifecycle smoke on the homelab.

## Alternatives considered

- **Inject a per-agent env file into the container.** Rejected: violates ADR-0002
  pull-at-boot and the no-secret-on-disk guarantee.
- **A separate external secrets service or vault per agent.** Rejected for self-host v1: the
  ADR-0015 Fernet store plus the reserved `KmsSecretKeyProvider` seam already cover the
  hosted escalation without a new dependency.
- **One shared bring-your-own-key env var reused across agents.** Rejected: each agent needs
  a differently scoped credential, and conflating them breaks least-privilege and the
  write-only, per-credential last4 status model.
- **Chosen:** extend the keyed store with a per-agent credential, add a non-secret `agent`
  selector, and swap the hardcoded launch constant for a registry lookup. Additive on every
  seam.

## Revisit trigger

An agent whose only container-viable auth is an interactive OAuth or refreshable device-flow
token (which the write-only store does not model and would force a token-refresh design), or
a requirement to run more than one agent concurrently inside a single worker (which reopens
ADR-0014's fixed single-tmux-session contract).

## References

- Cursor CLI headless mode and `CURSOR_API_KEY`: https://cursor.com/docs/cli/headless , https://cursor.com/docs/cli/overview
- GitHub Copilot CLI authentication (env vars, "Copilot Requests" PAT): https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli
- GitHub Copilot CLI programmatic reference (`copilot -p`) and repo: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference , https://github.com/github/copilot-cli
- OpenAI Codex CLI authentication and non-interactive mode (`codex exec`, API key): https://developers.openai.com/codex/auth , https://developers.openai.com/codex/noninteractive , https://www.npmjs.com/package/@openai/codex
- Internal: ADR-0002 (pull-at-boot bootconfig), ADR-0014 (tmux single-session), ADR-0015 (GUI-managed credential store), `api/lib/credentialResolver.py`, `api/services/workspaceService.py::mint_repo_credential`, `cc-worker-config/lxc/worker-template/burrow-boot.sh`, `cc-worker-config/plugins/manifest.schema.json`.
