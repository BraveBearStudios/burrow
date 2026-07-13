<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: passed
phase: 21
verified: 2026-07-13
---

# Phase 21: Multi-Agent Workers Research Spike - Verification

**Goal:** Produce a research-only ADR / design contract for running Cursor / Copilot
CLI / Codex CLI in workers (no build), confirming the v1.4 credential seam is additive
for future per-agent auth (AGENT-02).

## Must-Haves

1. **A reviewed research-only ADR is produced (no build)** - PASSED.
   `docs/adr/ADR-0018-multi-agent-worker-design-contract.md` exists (Status:
   Accepted, research-only), SPDX header present, `reuse lint-file` exit 0, no
   em/en-dashes. No `api/`, `ui/`, or `cc-worker-config/` product code changed.

2. **Each CLI's headless + auth model surveyed** - PASSED. Per-CLI findings for
   Cursor (`agent -p`, `CURSOR_API_KEY`), GitHub Copilot (`copilot -p`, GitHub PAT /
   `GH_TOKEN`), and Codex (`codex exec`, `OPENAI_API_KEY`), with sources cited and
   uncertain behaviors flagged UNVERIFIED.

3. **Additivity of the v1.4 credential seam confirmed (with evidence)** - PASSED. The
   ADR shows `getCredentialCiphertext(key: str)` is already string-keyed, so a
   per-agent secret is a new key + column/table via the unchanged `DbProvider` ABC,
   SecretBox, admin gate, and audit log. Three additive AGENT-03 surfaces named; no
   existing signature changes required.

## Evidence

- Artifact: `docs/adr/ADR-0018-multi-agent-worker-design-contract.md` (14.6K).
- `reuse lint-file` exit 0; em/en-dash grep clean.
- Sources: Cursor/Copilot/Codex official docs (cited in the ADR references).
- Seams read: credentialResolver, mint_repo_credential, getCredentialCiphertext,
  burrow-boot.sh, manifest.schema.json, ADR-0002/0014/0015.

**Verdict: PASSED** — the research-only deliverable is complete; the additive-seam
finding is evidenced; the build (AGENT-03+) is a documented future milestone.
