<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 21: Multi-Agent Workers Research Spike - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto (autonomous run). RESEARCH-ONLY — deliverable is a reviewed ADR-0018, NO build.

<domain>
## Phase Boundary

Produce a research-only ADR / design contract (ADR-0018) for running Cursor CLI /
GitHub Copilot CLI / Codex CLI inside Burrow workers, confirming the v1.4 credential
seam (ADR-0015 store + CredentialResolver + the pull-at-boot plugin manifest) is
ADDITIVE for future per-agent auth. No worker/boot/API code changes ship in this
phase; the build (AGENT-03+) is a future milestone (AGENT-02).
</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
Research-only phase — all findings + the design contract are at Claude's discretion,
grounded in the existing seams. The ADR must: (1) survey how each of the three CLIs
runs headless in a container + its auth model; (2) map each onto the existing worker
boot (`burrow-boot.sh` + the plugin manifest + ttyd) and the credential seam
(ADR-0015 store, `CredentialResolver`, `mint_repo_credential`); (3) prove the seam is
ADDITIVE (a future per-agent credential slots in without reworking the ABC/store/boot
contract); (4) record open questions + a recommended build order for AGENT-03+.
</decisions>

<code_context>
## Existing Code Insights
- ADR-0015 (credential store) + `api/lib/credentialResolver.py` + the `settings`
  credential columns are the per-secret seam a per-agent credential would extend.
- `cc-worker-config/lxc/worker-template/burrow-boot.sh` + the plugin manifest schema
  are how a worker installs + launches its agent today (Claude Code via ttyd/tmux).
- ADR-0002 (pull-at-boot) is the boot-config delivery contract.
</code_context>

<specifics>
## Specific Ideas
The ADR confirms additivity — it does NOT design the full per-agent auth (that is
AGENT-03+). Keep it a decision record + design contract, not an implementation plan.
</specifics>

<deferred>
## Deferred Ideas
The multi-agent BUILD (AGENT-03+) is a future milestone, explicitly out of scope.
</deferred>
