---
created: 2026-06-18T03:01:07.715Z
title: Support multiple AI coding agents in workers (Cursor, GitHub Copilot, Codex)
area: general
files:
  - cc-worker-config/lxc/worker-template/provision-template.sh
  - cc-worker-config/lxc/worker-template/burrow-boot.sh
  - cc-worker-config/plugins/manifest.json
  - api/ (WorkspaceCreate saga + DTO)
  - ui/ (NewWorkspaceModal)
---

## Problem

Burrow workers are hardwired to Claude Code. `provision-template.sh` bakes a pinned
`@anthropic-ai/claude-code` into the golden template and `burrow-boot.sh` execs ttyd
directly into the Claude Code terminal; the plugin manifest + schema are Claude-specific.
There is no way for an operator to spin up a worker running a different terminal AI coding
agent. Operators may want to run Cursor (cursor-agent / Cursor CLI), GitHub Copilot CLI,
or OpenAI Codex CLI in the same browser-tiled, ephemeral-container model Burrow already
provides for Claude Code.

The whole value prop ("manage many concurrent AI coding sessions from a browser") is
agent-agnostic in principle, but every layer currently assumes Claude Code: the worker
template, the boot script's exec target, the credential/bootconfig mint (repo-scoped git
cred only, no per-agent API key seam), and the create flow (no agent selector).

## Solution

TBD. Rough shape to evaluate when promoted:

- **Worker template:** either bake all supported agents into one golden template, or
  introduce per-agent templates / an install-at-boot step keyed by a selected agent.
  Decide reproducibility tradeoff (bake = fast/immutable vs install-at-boot = flexible),
  mirroring the existing plugin-cadence ADR-0009 reasoning.
- **Boot:** `burrow-boot.sh` execs ttyd into the chosen agent's launch command instead of a
  hardcoded `claude`. Needs an agent registry (launch cmd + env/secret requirements per agent).
- **Secrets seam:** today bootconfig only mints a short-lived repo-scoped git credential
  (no model API key reaches the worker). Cursor/Copilot/Codex need their own auth (API key /
  OAuth device flow). Extend the bootconfig mint seam additively, keep secrets off worker env
  per the existing SC-4 / credential-no-leak posture.
- **API/UI:** add an optional `agent` field to `WorkspaceCreate` (default = claude-code so
  existing behavior is unchanged) and an agent picker in `NewWorkspaceModal`, same pattern as
  the v1.2 Auto-node option that was added additively.
- **Scope:** likely a full milestone (v1.x/v2). Cross-cutting: cc-worker-config worker
  template + plugins, api create saga + DTO, ui create modal, and the bootconfig credential
  seam. Each agent's CLI maturity / headless-terminal support needs verification first
  (does it run cleanly under ttyd, non-interactive auth available, license terms allow it).
</content>
</invoke>
