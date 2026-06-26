---
status: human_needed
phase: 14-first-real-infra-acceptance
verified: 2026-06-26
score: automatable-slice-complete; ACC-01/02/03 await operator
---

# Phase 14 — Verification (First Real-Infra Acceptance)

**Status: `human_needed` by design.** Phase 14 is acceptance/runbook, not feature code. The
ROADMAP marks it CI-provable: **NO** — ACC-01/02/03 require the operator's real Proxmox homelab and a
first live signed release, which CI never exercises. The automatable slice landed and is verified
structurally; the real-infra acceptance itself is the operator's gate and is NOT auto-passed.

## Automatable slice — verified (CI-provable / structural)

| Item | Evidence | Status |
|------|----------|--------|
| actionlint wired into CI (ACC-02) | `ci.yml` static-gates runs a SHA-pinned `reviewdog/action-actionlint@<40-hex>` step, fail-fast after Checkout (`rhysd/actionlint` ships no `action.yml`; the documented reviewdog action was substituted). Proven by the first live CI run. | landed |
| harden-runner allowlist-prep + audit preserved (ACC-02 c3) | all five jobs keep `egress-policy: audit`; commented allowlist-prep (Fulcio/Rekor/TUF/OIDC/GHCR) + a flip pointer added; `block` appears only in comments | landed |
| Publish path untouched + already-correct | `release.yml` publish job byte-unchanged: exactly 4 perms (contents:read, packages:write, id-token:write, attestations:write), verify-by-digest, cosign keyless sign + dual SBOM + SLSA attest, all `uses:` SHA-pinned | confirmed |
| Workflows valid | `python yaml.safe_load` parses all three workflows; every `uses:` 40-hex SHA-pinned; `reuse lint` clean | green |
| 14-ACCEPTANCE.md runbook (ACC-02/03) | cosign verify + gh attestation verify BY `@sha256:` digest, the gh-attestation exit-0 trap (assert on OUTPUT), verify-by-digest-not-tag, the audit→block flip procedure, the 4-perms + SHA-pin checklist, actionlint; each ACC item has command + expected + PASS/FAIL; 0 em dashes | authored |
| 14-HUMAN-UAT.md consolidated checklist | 16 items across ACC-01/02/03 (H9 five-step gate + reaper/auto-stop/capacity/node + persistent stop→start with disk + scrollback + live release + cosign/attestation); all `result: [pending]`; rolls up Phase 03/04 | authored |
| Phase 03/04 HUMAN-UAT superseded | additive superseded-by-v1.3-Phase-14 notes; original items + results unchanged | done |

## Human verification required (ACC-01/02/03 — operator-run on real infra)

These are the open gate. The operator runs them from `14-HUMAN-UAT.md` and `14-ACCEPTANCE.md`, then
flips the items to passed:

1. **ACC-01 (homelab smoke):** the H9 five-step gate (create→terminal→stop→start→destroy) on real
   Proxmox + reaper/auto-stop/capacity/real least-loaded node selection on real CTs.
2. **ACC-01 (WSX-02/03 live proof):** a real persistent workspace survives a real stop→start with its
   disk intact AND its terminal scrollback restored on reconnect; the reaper never destroys a
   persistent stopped workspace on real CTs.
3. **ACC-02 (first live release):** the first release-please PR merges (version bump + changelog + v*
   tag); harden-runner egress flipped `audit`→`block` with the discovered allowlist; actionlint passes
   on the live runner.
4. **ACC-03 (real signed release):** real GHCR publish + `cosign verify` + `gh attestation verify`
   pass against the published `@sha256:` digest (by digest, asserting on output).

Host-prime prerequisites must be operator-confirmed first (PRIMING.md P1-P5 + the STEP 0-3 scripts).

## Routing

Phase 14 stays **pending / human_needed** until the operator passes the real-infra UAT. The milestone
lifecycle (audit → complete → cleanup) is DEFERRED until then — the v1.3 milestone is not truly
complete until ACC-01/02/03 pass on real hardware. No automated check can flip this.
