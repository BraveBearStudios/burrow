---
phase: 8
slug: release-hardening-release-please-harden-runner
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> This phase ships CI-config + docs only (no api/ui code). Validation is
> static parse of the authored YAML/JSON + the existing SPDX/REUSE lint gate.
> Live release-please PR + live harden-runner enforcement are the deferred
> ACC-02 on-runner acceptance (by design — not dev-box-runnable).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None new — Python stdlib `yaml`/`json` parse + `uvx --with charset-normalizer reuse lint` (existing CICD-06 gate) |
| **Config file** | none |
| **Quick run command** | `python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/release-please.yml .github/workflows/ci.yml .github/workflows/release.yml` |
| **Full suite command** | `python -c "import json; json.load(open('release-please-config.json')); json.load(open('.release-please-manifest.json'))" && uvx --with charset-normalizer reuse lint` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick command (YAML parse of the 3 workflows)
- **After every plan wave:** Run the full suite (JSON parse + `reuse lint`)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 1 | RELX-01 | — | `release-please.yml` valid YAML, trigger `push: branches:[main]`, perms `contents:write`+`pull-requests:write` | static-parse | `python -c "import yaml; d=yaml.safe_load(open('.github/workflows/release-please.yml')); assert 'main' in d['on']['push']['branches']"` | ❌ W0 | ⬜ pending |
| 8-01-02 | 01 | 1 | RELX-01 | — | `release-please-config.json` parses, `release-type:simple`, package `"."` | static-parse | `python -c "import json; c=json.load(open('release-please-config.json')); assert c['release-type']=='simple' and '.' in c['packages']"` | ❌ W0 | ⬜ pending |
| 8-01-03 | 01 | 1 | RELX-01 | — | `.release-please-manifest.json` seeds root version `1.1.0` | static-parse | `python -c "import json; m=json.load(open('.release-please-manifest.json')); assert m['.']=='1.1.0'"` | ❌ W0 | ⬜ pending |
| 8-02-01 | 02 | 2 | RELX-02 | T-08-01 | harden-runner is step 0 of every job in all 3 workflows, `egress-policy:audit` | static-parse | `python` per-job assertion: `steps[0]['uses'].startswith('step-security/harden-runner@')` and `steps[0]['with']['egress-policy']=='audit'` | ❌ W0 | ⬜ pending |
| 8-02-02 | 02 | 2 | RELX-02 | T-08-02 | every `uses:` pinned to a 40-char SHA (no floating `@vN` tags) | static-parse | regex over the 3 workflow files: each `uses:` ref after `@` matches `[0-9a-f]{40}` | ❌ W0 | ⬜ pending |
| 8-02-03 | 02 | 2 | RELX-02 | T-08-02 | PR-title gate repinned off the moving `v5` tag to a real release SHA | static-parse | assert amannn `uses:` SHA != `e32d7e60…` and matches `[0-9a-f]{40}` | ❌ W0 | ⬜ pending |
| 8-03-01 | 03 | 2 | RELX-01/02 | — | SPDX/REUSE green incl. the two new comment-less JSON files | lint | `uvx --with charset-normalizer reuse lint` | ✅ (gate exists; REUSE.toml gains 2 paths) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- No test-framework install — this phase authors CI config + docs; there is no api/ui test code.
- Validation is the static-parse + `reuse lint` commands above, runnable on the dev box once the files exist.

*Existing infrastructure (Python + the `reuse` gate) covers all dev-box-runnable phase validation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First live release-please PR opens with a v1.2.0 bump + generated changelog | RELX-01 | Needs a real GitHub Actions runner + a push to main (deferred ACC-02) | On first push to main after merge, confirm a "chore(main): release 1.2.0" PR appears; merge it and confirm a `v1.2.0` tag is created. |
| The `v*` tag from release-please fires `release.yml`'s publish job | RELX-01 | `GITHUB_TOKEN`-raised tag events may not re-trigger workflows (Open Q1) | On first release, verify `release.yml` runs on the new tag; if not, apply the ACC-02 remediation (scoped GitHub App token or manual re-run). |
| harden-runner `block` enforcement + discovered egress allowlist | RELX-02 | Audit→block flip needs the real audit telemetry from a live runner (deferred ACC-02) | After audit runs accumulate, read the StepSecurity insights, author `allowed-endpoints`, flip `egress-policy: block`. |

---

## Validation Sign-Off

- [ ] All tasks have an automated static-parse/lint verify or are explicitly Manual-Only (ACC-02)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (N/A — no test framework)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
