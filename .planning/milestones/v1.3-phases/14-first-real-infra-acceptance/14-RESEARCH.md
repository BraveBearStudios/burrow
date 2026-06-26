# Phase 14: First Real-Infra Acceptance - Research

**Researched:** 2026-06-26
**Confidence:** HIGH — codebase claims verified by scout against the live workflows; the cosign/GHCR/harden-runner traps are well-understood and most are already correctly implemented.

## What must be true (ACC-01/02/03)

(1) Real homelab create→terminal→stop→start→destroy lifecycle (H9) + reaper/auto-stop/capacity/node
selection on real CTs; (2) a real persistent workspace survives a real stop→start with disk + scrollback
restored; (3) the first live release-please PR merges (version bump + changelog + v* tag), harden-runner
egress flipped audit→block with the discovered allowlist, actionlint passes; (4) real GHCR publish +
cosign verify + gh attestation verify pass against the published @sha256 digest.

**CI-provable: NO.** Criteria 1, 2, 4 and the merge/flip half of 3 are operator-run on real infra/live
release. The AUTOMATABLE slice this run delivers: actionlint wired into CI, harden-runner allowlist-prep +
flip documentation (egress stays audit), and the acceptance/release runbook + consolidated UAT checklist.
Phase 14 verification lands `human_needed`; the run stops for the operator.

## Already-correct (do NOT touch — scout-verified)

- release.yml has EXACTLY 4 publish perms (`contents:read, packages:write, id-token:write,
  attestations:write`, :44-48). Trap 2 DONE.
- Verify-by-digest: build-push outputs `steps.build.outputs.digest`; SBOM/cosign/attest all target
  `@${{ steps.build.outputs.digest }}` (:107-144). Trap 1 DONE.
- cosign keyless sign + SLSA build-provenance attest + SPDX/CycloneDX SBOM, all SHA-pinned (25 `uses:`).
- release-please-config.json (simple, include-v-in-tag, bootstrap-sha) + manifest ".":"1.1.0".

## The automatable work

### 1. actionlint in CI (ACC-02)
Add a SHA-pinned actionlint step to `ci.yml`'s `static-gates` job. actionlint validates GitHub Actions
workflow schema/expressions. It is NOT installable on the Windows dev box (Phase 8 RELX-02 deferral), so
LOCAL verification is limited to: the workflow YAML still parses (Python `yaml.safe_load`), the SHA-pin
regex holds, reuse/SPDX lint clean. The actionlint RUN itself is proven by the first live CI run. Use a
pinned action (e.g. `rhysd/actionlint`) or a pinned container; keep it fail-fast in static-gates. This is
the honest contract: author + structurally validate now; live CI proves the lint pass.

### 2. harden-runner allowlist-prep + flip doc (ACC-02 criterion 3)
Egress stays `audit` on all five jobs (no functional change). Add a COMMENTED placeholder allowlist next
to each `egress-policy: audit` listing the cosign endpoints the block-flip will need:
`fulcio.sigstore.dev`, `rekor.sigstore.dev`, `tuf.sigstore.dev`,
`token.actions.githubusercontent.com` (OIDC), plus `ghcr.io` / `*.actions.githubusercontent.com` /
`github.com` / `objects.githubusercontent.com` as typical. The runbook documents: run the workflow once
on a real tag → read the harden-runner audit (Step Security insights / the run's annotations) → fill the
real `allowed-endpoints` → flip `egress-policy: block` → re-run and confirm green. Do NOT flip to block
with a guessed list (a missing Fulcio/Rekor/TUF endpoint silently breaks keyless signing).

### 3. gh attestation verify exit-0 trap (runbook)
`gh attestation verify` can exit 0 even when verification is meaningless (a known CLI quirk). The runbook
MUST instruct the operator to assert on OUTPUT (look for the explicit success line / inspect the JSON),
not just `$?`. Pair with `cosign verify` (which fails loudly) for defense in depth.

### 4. The runbook + UAT (docs)
- `14-ACCEPTANCE.md`: the release/verify runbook — the audit→block flip procedure, the cosign verify +
  gh attestation verify commands (by digest, with the exit-0 assertion), the verify-by-digest-not-tag
  rule, the 4-perms + SHA-pin checklist, and the actionlint gate. Each criterion: exact command +
  expected output + pass/fail.
- `14-HUMAN-UAT.md`: consolidated ACC-01/02/03 checklist mirroring PRIMING.md STEP 4 (the H9 five-step
  gate) + the persistent stop→start + scrollback proof + the live-release verify. Rolls up the still-
  pending Phase 03 + 04 HUMAN-UAT items (mark those superseded-by-v1.3-Phase-14).

## Pitfalls

- Do NOT flip harden-runner to `block` without the discovered allowlist — it breaks the live cosign run.
- Do NOT claim actionlint passes locally (it cannot run on the Windows dev box) — the first live CI run is
  its proof; verify the YAML structurally instead.
- Do NOT rework the already-correct publish job (4 perms / by-digest / cosign) — only ADD actionlint +
  allowlist comments.
- Do NOT auto-pass Phase 14 verification — ACC-01/02/03 are real-infra; the run lands human_needed.
- Do NOT run the milestone lifecycle (audit/complete/cleanup) — the milestone is not done until the
  operator passes the real-infra UAT.
- gh attestation verify: assert on output, not exit code.

## Validation Architecture

**Framework:** structural only for the automatable CI slice (the real gates are operator-run on infra).
- actionlint step: the workflow still `yaml.safe_load`s; the new step is well-formed; SHA-pin regex holds;
  `reuse lint` / SPDX clean. (actionlint itself runs on live CI — manual-only here.)
- The runbook + UAT are docs — verified by review (every ACC criterion has a command + expected output +
  pass/fail line), not by an automated test.

**Manual-only / operator-gated (the heart of this phase):**
- ACC-01 homelab H9 five-step gate + reaper/auto-stop/capacity/node-selection on real CTs.
- ACC-02 first live release-please merge + harden-runner block flip with the discovered allowlist +
  actionlint pass on the live runner.
- ACC-03 real GHCR publish + cosign verify + gh attestation verify (by digest, assert on output).

**Disposition:** Phase 14 verification = `human_needed`. The autonomous run stops at the human gate; the
operator executes the real UAT + live release from the homelab, then flips the UAT items to passed.

**Security (ASVS L1):** the publish path is already hardened (4 perms, keyless sign, SHA-pins,
by-digest). This phase ADDS defense (actionlint catches workflow misconfig; the audit→block flip
tightens egress). No secret handling changes; the PVE token stays `.env`-only (Phase 12 gate). No new
HIGH threat.

## RESEARCH COMPLETE
