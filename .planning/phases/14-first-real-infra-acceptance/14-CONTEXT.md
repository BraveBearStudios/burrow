# Phase 14: First Real-Infra Acceptance - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Burrow is proven to actually run on the operator's real Proxmox homelab and to publish a real,
verifiable signed release — the human-UAT acceptance gate that flips the long-carried real-infra
items (and the per-phase `*-HUMAN-UAT.md` checklists) to passed. Requirements: ACC-01, ACC-02,
ACC-03. **CI-provable: NO** — operator-run human UAT on real Proxmox + a first live GHCR/cosign
release; CI never touches real Proxmox by design. This phase is acceptance/runbook, not feature code.

The AUTOMATABLE slice (this run delivers): the acceptance/release runbook (`14-ACCEPTANCE.md`), the
consolidated UAT checklist (`14-HUMAN-UAT.md`), an `actionlint` CI step, and harden-runner
allowlist-prep + flip documentation. The OPERATOR-GATED slice (deferred to the operator on real
hardware): the homelab smoke (ACC-01), the first live release-please merge + harden-runner block
flip with the discovered allowlist (ACC-02), and the real GHCR publish + cosign/attestation verify
(ACC-03). Phase 14 verification lands `human_needed` and the autonomous run STOPS there — the
milestone lifecycle (audit/complete/cleanup) is deferred until the operator passes the real-infra UAT.
</domain>

<decisions>
## Implementation Decisions

### Automatable code/CI scope
- **actionlint (ACC-02):** add a SHA-pinned `actionlint` step to `ci.yml`'s `static-gates` job (run
  early, fail fast). It runs on GitHub's Linux runner; it cannot be verified on the Windows dev box
  (Phase 8 RELX-02 deferral reason), so the first live CI run is its proof. Author it now.
- **harden-runner `audit→block` (ACC-02 criterion 3):** KEEP `egress-policy: audit` on all five jobs
  (ci.yml static-gates/pr-title/build-scan, release.yml publish, release-please.yml). Add a commented
  placeholder allowlist showing the typical cosign endpoints (Fulcio
  `https://fulcio.sigstore.dev`, Rekor `https://rekor.sigstore.dev`, TUF
  `https://tuf.sigstore.dev`, plus `token.actions.githubusercontent.com`) and document the flip
  procedure in the runbook. Do NOT flip to `block` with a guessed allowlist — the real allowlist must
  be discovered from the operator's first live audit run, or `block` will break the live release.
- **`gh attestation verify` exit-0 trap:** document in the runbook that the operator must ASSERT ON
  OUTPUT (not just the exit code) — `gh attestation verify` can exit 0 on a malformed attestation.
  Locked by the STATE hard gate.
- **No structural change** to the already-correct publish path: release.yml already has exactly 4
  publish perms (contents:read, packages:write, id-token:write, attestations:write), verify-by-digest
  (every step targets `@${{ steps.build.outputs.digest }}`), cosign keyless sign + SBOM + SLSA
  attest, and all third-party `uses:` SHA-pinned. Traps 1 (by-digest) and 2 (4 perms) are DONE — do
  not rework them.

### Acceptance artifacts + run disposition
- New `14-…` phase dir holds `14-ACCEPTANCE.md` (the release/verify runbook) + `14-HUMAN-UAT.md` (the
  consolidated checklist). Both are operator-executed.
- `14-HUMAN-UAT.md` consolidates ACC-01/02/03: the H9 five-step homelab gate
  (create→terminal→stop→start→destroy + reaper/auto-stop/capacity/real-node-selection), the real
  persistent stop→start with disk intact AND scrollback restored (live proof of WSX-02 + WSX-03 +
  the reaper carve-out), and the live-release verify (release-please merge → v* tag → GHCR publish →
  cosign verify + gh attestation verify by digest). It rolls up the still-pending Phase 03 + Phase 04
  HUMAN-UAT items (mark those as superseded-by-v1.3-Phase-14).
- `14-ACCEPTANCE.md` is the release runbook: the harden-runner audit→block flip procedure (discover
  allowlist → fill → flip → re-run), the cosign verify + gh attestation verify commands (by digest,
  with the exit-0 output-assertion anti-pattern), the verify-by-digest-not-tag rule, the exactly-4-perms
  + SHA-pin checklist, and actionlint.
- **Verification disposition:** Phase 14's automated verification lands `human_needed` — the artifacts
  + CI hardening are CI-provable, but ACC-01/02/03 themselves require real infra. The run stops at the
  human-verification gate; it does NOT auto-pass.
- **Milestone lifecycle deferred:** do NOT auto-run milestone audit/complete/cleanup tonight — the
  v1.3 milestone is not truly complete until the operator passes the real-infra UAT.

### Claude's Discretion
- Exact actionlint action choice (e.g. a pinned `rhysd/actionlint` or a container step) and its
  placement within static-gates, at the implementer's discretion (SHA-pinned, fail-fast).
- The precise prose/format of the runbook + checklist, as long as every ACC criterion has explicit
  commands, expected output, and a pass/fail line.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml` (static-gates :30, pr-title :121, build-scan :155; harden-runner audit
  at :30-32/:121-123/:155-157) — add the actionlint step to static-gates.
- `.github/workflows/release.yml` (publish job; 4 perms :44-48; cosign/SBOM/attest :107-144;
  verify-by-digest; verification runbook comment :146-165; harden-runner audit :59-61).
- `.github/workflows/release-please.yml` (release-please job; harden-runner audit :44-46).
- `release-please-config.json` (simple, include-v-in-tag, bootstrap-sha) + `.release-please-manifest.json`
  (".": "1.1.0").
- `cc-worker-config/PRIMING.md` — Day-0 operator runbook; STEP 4 (:88-110) is the H9 five-step
  acceptance gate; preconditions P1-P5 (:22-30).
- `docs/ci-cd-and-testing.md` §5.4 (SBOM/sign/provenance :283-296), §5.5 (runner hardening :298-308),
  §6 (release versioning :312-321).
- Existing `03-HUMAN-UAT.md` (5 items pending) + `04-HUMAN-UAT.md` (5 items pending) — roll up into 14.
- STATE.md deferred rows :205-213 (the ACC-claimed real-infra + release rows).

### Established Patterns
- All third-party actions SHA-pinned; per-job `permissions:`; harden-runner per job; SPDX headers;
  conventional commits drive release-please; no em dashes; reuse lint for SPDX.

### Integration Points
- `.github/workflows/ci.yml` — actionlint step.
- `.github/workflows/release.yml` + `release-please.yml` — commented allowlist placeholder + flip doc
  (egress stays audit).
- NEW `.planning/phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md` + `14-HUMAN-UAT.md`.
- 03/04-HUMAN-UAT.md — mark superseded-by-v1.3-Phase-14.
</code_context>

<specifics>
## Specific Ideas

- Traps 1+2 (by-digest, 4 perms) are already correct in release.yml — Phase 14 only adds trap-3
  (exit-0 assertion doc) + trap-4 (allowlist-prep + flip doc) + actionlint.
- The H9 five-step gate (PRIMING.md STEP 4) is the canonical homelab smoke; 14-HUMAN-UAT.md mirrors it
  and adds the persistent stop→start + scrollback proof and the live-release verify.
- This run STOPS at human_needed; the operator runs the real UAT + live release from the homelab.
</specifics>

<deferred>
## Deferred Ideas

- The actual homelab smoke (ACC-01), first live release merge + harden-runner block flip with the real
  allowlist (ACC-02), and real GHCR publish + cosign/attestation verify (ACC-03) — OPERATOR-RUN on real
  infra; not automatable.
- Milestone audit/complete/cleanup — deferred until the operator passes the real-infra UAT.
- WSX-05/06/07 snapshots/CRIU/cross-reboot scrollback + AGENT-01 multi-agent — v1.4+ (unchanged).
</deferred>
