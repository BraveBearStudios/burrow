---
phase: 14
slug: first-real-infra-acceptance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-26
---

# Phase 14 — Validation Strategy

> Per-phase validation contract. This phase is acceptance/runbook: most validation is MANUAL-ONLY
> (operator-run on real infra). The automatable CI slice is structurally validated only.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | structural workflow checks (Python `yaml.safe_load`, SHA-pin regex, `reuse lint`); doc review. actionlint runs on the live GitHub runner only (unavailable on the Windows dev box). |
| **Config file** | `.github/workflows/*.yml`, `release-please-config.json` |
| **Quick run command** | `python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"` (workflows parse) |
| **Full suite command** | the above + `uvx --with charset-normalizer reuse lint` (SPDX) |
| **Estimated runtime** | seconds |

---

## Sampling Rate

- **After every task commit:** the workflow-parse check (for workflow edits) / doc review (for runbook/UAT).
- **Before `/gsd:verify-work`:** workflows parse, SHA-pins intact, SPDX clean.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-xx | ci-hardening | 1 | ACC-02 | — | actionlint step added; harden-runner stays audit + allowlist-prep comments; workflows parse; SHA-pins intact | structural | `python -c "import yaml,glob;[yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"` | ✅ | ⬜ pending |
| 14-02-xx | acceptance-runbook | 1 | ACC-01/02/03 | — | 14-ACCEPTANCE.md + 14-HUMAN-UAT.md author all ACC criteria with command+expected+pass/fail; no em dashes | doc review | `test -f .planning/phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `14-ACCEPTANCE.md` (release/verify runbook) + `14-HUMAN-UAT.md` (consolidated ACC checklist) authored.
- [ ] actionlint step in ci.yml static-gates (SHA-pinned); workflows still parse; SHA-pin regex holds.

*No new framework — structural checks + doc review only.*

---

## Manual-Only Verifications (the heart of this phase — OPERATOR-RUN on real infra)

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real homelab H9 five-step gate (create→terminal→stop→start→destroy) + reaper/auto-stop/capacity/real node selection on real CTs | ACC-01 | Real Proxmox only | `14-HUMAN-UAT.md` / PRIMING.md STEP 4 |
| Real persistent workspace survives a real stop→start with disk intact + scrollback restored on reconnect | ACC-01 (WSX-02/03 live proof) | Real Proxmox only | `14-HUMAN-UAT.md` |
| First live release-please PR merges → version bump + changelog + v* tag; harden-runner egress flipped audit→block with the discovered allowlist; actionlint passes on the live runner | ACC-02 | Live GitHub Actions only | `14-ACCEPTANCE.md` |
| Real GHCR publish + `cosign verify` + `gh attestation verify` pass against the published `@sha256:` digest (by digest, assert on output) | ACC-03 | Live registry only | `14-ACCEPTANCE.md` |

*This phase's verification is `human_needed` by design. The autonomous run STOPS at the human gate; the operator executes the real UAT + live release, then flips the UAT items to passed.*

---

## Validation Sign-Off

- [ ] Automatable tasks have a structural `<automated>` check or are doc-review Wave 0 items
- [ ] All four ACC behaviors captured as manual-only operator verifications
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter (note: this phase is acceptance — manual verification is expected and correct, not a sampling gap)

**Approval:** pending
