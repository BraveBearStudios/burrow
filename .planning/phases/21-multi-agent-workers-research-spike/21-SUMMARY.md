<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 21: Multi-Agent Workers Research Spike - Summary

**Completed:** 2026-07-13
**Requirement:** AGENT-02 · **ADR:** ADR-0018 (research-only, no build)

## Deliverable

`docs/adr/ADR-0018-multi-agent-worker-design-contract.md` — a research-only design
contract (Status: Accepted, research-only; ships no product code).

## Findings

- **All three CLIs run headless in a Linux container:** Cursor `agent -p`, GitHub
  Copilot `copilot -p`, OpenAI Codex `codex exec`, each with a JSON output mode.
- **One container-friendly auth shape shared by all:** a single opaque secret in an
  env var (`CURSOR_API_KEY`, `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`, `OPENAI_API_KEY`).
  Each also has an interactive OAuth login that is NOT container-friendly.
- **Maps onto what Burrow already stores:** Copilot needs a fine-grained GitHub PAT
  (the same shape the store already holds, "Copilot Requests"-scoped) + a live
  subscription; Cursor + Codex need opaque API keys.
- **Install fits the existing plugin manifest with no schema change** (Cursor as
  `binary`, Copilot/Codex as `npm-global`), baked at provision time. The only
  Claude-hardcoded coupling in the boot path is `CLAUDE_CMD="claude"` + the final
  `exec`; the rest (bootconfig pull, credential mint, ttyd/tmux) is agent-agnostic.

## Verdict: the v1.4 credential seam IS additive

`DbProvider.getCredentialCiphertext(key: str)` is already keyed by a credential
string, so a per-agent secret is a new key + a new column set (or an
`agent_credentials` table) reached through the UNCHANGED seam — no rewrite of the
`DbProvider` ABC, the SecretBox/Fernet crypto, the `require_admin` gate, or the
`audit_log`. AGENT-03 adds three additive surfaces only: (a) new store key +
`CredentialResolver.agent_secret` + an admin-gated write endpoint; (b) a non-secret
`agent` field on `WorkspaceCreate`/bootconfig/create-modal driving a launch selector
in `burrow-boot.sh`; (c) the minted per-agent secret as a new bootconfig `.data`
field exported as the agent's env var before `exec`. No existing signature changes.

## Open questions (recorded in the ADR)

Cursor `-p` behavior under ttyd/tmux; Codex device-code sign-in admin gating; Codex
plaintext `~/.codex/auth.json`; a future OAuth-device-flow-only agent (which the
write-only store would not model) — the ADR's revisit trigger. All flagged
UNVERIFIED, to be smoke-tested when AGENT-03 builds.

## Verification

Research-only; the ADR is the artifact. `reuse lint-file` exit 0 (SPDX header
present), no em/en-dashes. Sources cited inline (Cursor/Copilot/Codex official docs).
