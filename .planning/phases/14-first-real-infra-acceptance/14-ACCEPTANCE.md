<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: pending
phase: 14-first-real-infra-acceptance
source: [14-RESEARCH.md, release.yml, ci.yml]
created: 2026-06-26T00:00:00Z
requirements: [ACC-02, ACC-03]
---

# Phase 14 Acceptance: Release and Verify Runbook (ACC-02 / ACC-03)

This is the operator runbook for the **live release** and **signature/provenance verify**
half of Phase 14. It is run once, by a human (or release automation), against the first
real `v*` tag and the resulting published GHCR digest. CI never executes these steps: they
need a live registry, OIDC, and the Step Security insights for a real run, so they are
`human_needed` by design.

Every step gives the EXACT command, the EXPECTED output, and an explicit PASS / FAIL line.
Substitute your repo owner (`<owner>`, the committed placeholder is `BraveBearStudios`) and
the real published manifest digest (`<digest>`) where shown.

## How to read this runbook

- ACC-02 is "the first live release-please PR merges, harden-runner egress is flipped
  `audit` to `block` with the discovered allowlist, and `actionlint` passes."
- ACC-03 is "a real GHCR publish succeeds and `cosign verify` plus `gh attestation verify`
  pass against the published `@sha256:` digest."
- Verify BY DIGEST, never by tag. A tag (`:latest`, `:v1.3.0`) is mutable and can be
  re-pointed; the `@sha256:<digest>` is the immutable manifest. Every verify command below
  targets the digest for exactly this reason.

## Preconditions (operator confirms before starting)

| ID | Precondition |
|----|--------------|
| PC1 | The v1.3 build is green on `main` (CI passing, including the `actionlint` static gate). |
| PC2 | release-please has an open release PR on `main` (the version-bump / CHANGELOG PR). |
| PC3 | You can merge to `main` and have `cosign` and the `gh` CLI installed locally (or a runner). |
| PC4 | The PVE token stays `.env`-only; it is NOT needed for ACC-02 / ACC-03 and never leaves `.env`. |

## ACC-02: first live release

### Step A: merge the release-please PR

The release-please PR, once merged, bumps the version in the manifest, regenerates the
CHANGELOG, and pushes the `vX.Y.Z` tag. The `v*` tag is what triggers `release.yml`.

```bash
# Merge the open release-please PR (squash; the title is already a valid Conventional Commit).
gh pr merge <release-please-pr-number> --squash --repo <owner>/burrow
```

**Expected output:** the PR merges; release-please then pushes a version-bump commit, a
regenerated `CHANGELOG.md` entry, and a `vX.Y.Z` git tag. Confirm the tag exists:

```bash
git fetch --tags && git tag --list 'v*' --sort=-creatordate | head -n 1
```

Expected: the new `vX.Y.Z` tag is printed as the most recent tag.

**PASS:** a version-bump commit, a new CHANGELOG entry, and a `vX.Y.Z` tag all exist.
**FAIL:** no tag is pushed, or the CHANGELOG / version bump is missing.

### Step B: confirm the v\* tag triggered release.yml and it is green

```bash
gh run list --repo <owner>/burrow --workflow release.yml --limit 1
```

**Expected output:** one `release.yml` run keyed to the `vX.Y.Z` tag, with conclusion
`success` (green). Open it and confirm the publish job (the `build-publish` matrix for
`burrow-api` and `burrow-ui`) completed.

**PASS:** the `release.yml` run for the `vX.Y.Z` tag is green and the publish job ran for
both images.
**FAIL:** the run is red, was not triggered, or the publish job was skipped.

### Step C: actionlint gate passes on the live runner

`actionlint` (wired in 14-01 as the SHA-pinned `reviewdog/action-actionlint` step in the
`static-gates` job of `ci.yml`) cannot run on the Windows dev box, so the live CI run is its
real proof. Confirm it executed and passed.

```bash
# Inspect the static-gates job of the latest green ci.yml run on the release commit.
gh run view <ci-run-id> --repo <owner>/burrow --log | grep -i "actionlint"
```

**Expected output:** the `actionlint` step (configured `reporter: github-check`,
`fail_level: error`) runs and reports no workflow schema or expression errors; the step
conclusion is success. A real workflow error would fail the step (it is a fail-fast gate,
not advisory).

**PASS:** the `actionlint` step ran and passed on the live Linux runner.
**FAIL:** the step was skipped, errored, or only emitted advisory annotations without
gating.

### Step D: harden-runner audit to block flip (ACC-02 criterion 3)

Egress stays `egress-policy: audit` in the repo (set on all five harden-runner steps in
`ci.yml` and `release.yml`). The allowlist is seeded as inert YAML comments below each
`egress-policy: audit` (the 14-01 allowlist-prep block). Do NOT flip to `block` with a
guessed allowlist: a missing Fulcio / Rekor / TUF endpoint silently breaks keyless signing.

Flip procedure (run in this exact order):

1. **Run once in audit on the real tag.** The Step B `release.yml` run (egress `audit`)
   already produced the audit telemetry. No extra run is needed if Step B is green.

2. **Read the discovered egress allowlist.** Open the Step Security insights for that run
   (the harden-runner annotations on the run, or the insights link in the job summary) and
   read the outbound endpoints the job actually contacted.

3. **Fill `allowed-endpoints` from the placeholder.** Uncomment the seeded
   `allowed-endpoints` block under each `egress-policy` and populate it with the discovered
   endpoints. The publish job (keyless sign + SLSA attest + GHCR push) needs at minimum
   these seven, each on `:443`:

   ```yaml
   allowed-endpoints: |
     fulcio.sigstore.dev:443
     rekor.sigstore.dev:443
     tuf.sigstore.dev:443
     token.actions.githubusercontent.com:443
     ghcr.io:443
     github.com:443
     objects.githubusercontent.com:443
   ```

   Add any additional endpoints the audit surfaced (for example
   `*.actions.githubusercontent.com:443`). `fulcio.sigstore.dev` and `rekor.sigstore.dev`
   are keyless-signing-critical: omitting either breaks `cosign sign`.

4. **Flip `egress-policy: audit` to `egress-policy: block`** in all five jobs (the three in
   `ci.yml`: `static-gates`, `pr-title`, `build-scan`; plus `release.yml` publish and
   `release-please.yml`).

5. **Re-run and confirm green.** Push the change, re-run `release.yml` (a fresh patch tag,
   or re-run the workflow), and confirm the block-mode run still signs and publishes.

**Expected output:** the block-mode `release.yml` run is green, the images publish, and
`cosign sign` plus the SLSA attestation succeed (no blocked-egress failures in the
harden-runner annotations).

**PASS:** ONLY if the block-mode run is green and still produces signed, attested,
published images.
**FAIL:** any harden-runner blocked-egress error, or a failed sign / attest / push after the
flip (revert to `audit`, re-read the allowlist, and retry; do not ship with a broken flip).

## ACC-03: GHCR publish and signature / provenance verify

Run these against the PUBLISHED manifest digest from the Step B publish run. Get the digest
from the run logs (the `Build and push (by digest)` step output, `steps.build.outputs.digest`)
or by inspecting the registry. Substitute it as `<digest>` below. Run the pair for BOTH
`burrow-api` and `burrow-ui`.

### Step E: cosign verify (keyless, fails loudly) (mirror of release.yml verify runbook)

```bash
cosign verify \
  --certificate-identity-regexp 'https://github.com/<owner>/burrow/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/<owner>/burrow-api@sha256:<digest>
```

**Expected output:** cosign prints the verification summary and the claims it checked
(the Fulcio certificate identity matched the regexp, the OIDC issuer matched
`token.actions.githubusercontent.com`, and the Rekor transparency-log entry was found),
then exits 0. cosign FAILS LOUDLY (non-zero exit, no summary) on a bad signature, a wrong
identity, or a missing Rekor entry, which is exactly why it is the primary gate.

**PASS:** cosign prints the verified-claims summary and exits 0 for both `burrow-api` and
`burrow-ui` at their digests.
**FAIL:** cosign exits non-zero or prints no verified-claims summary.

### Step F: gh attestation verify (assert on OUTPUT, not exit code)

```bash
gh attestation verify \
  oci://ghcr.io/<owner>/burrow-api@sha256:<digest> \
  --owner <owner>
```

**Expected output:** `gh` prints an explicit success / verified line (for example
"Loaded ... attestations" then a "verification succeeded" / "sLSA ... verified" line) and
the matched SLSA build-provenance predicate.

**CRITICAL TRAP (T-14-01):** `gh attestation verify` can EXIT 0 even when the verification
is meaningless. Do NOT trust the exit code (`$?`) alone. You MUST assert on the OUTPUT: read
the explicit success / verified line and inspect the predicate, and run with `--format json`
to inspect the JSON when in doubt:

```bash
gh attestation verify \
  oci://ghcr.io/<owner>/burrow-api@sha256:<digest> \
  --owner <owner> --format json | jq '.[].verificationResult.signature.certificate'
```

Confirm the JSON shows the expected signer identity and the SLSA provenance predicate bound
to your `@sha256:<digest>`. Because `gh` can exit 0 spuriously, the `cosign verify` in Step E
(which fails loudly) is the paired defense-in-depth gate: treat a passing ACC-03 as requiring
BOTH a loud-passing cosign verify AND an output-asserted attestation verify.

**PASS:** the attestation output explicitly states verification succeeded, the JSON shows the
expected signer and the SLSA provenance predicate bound to the digest, AND Step E (cosign)
passed for the same digest.
**FAIL:** the output lacks an explicit verified line, the JSON predicate or signer is wrong or
missing, or it does not bind to your `@sha256:<digest>` (regardless of a 0 exit code).

## Standing invariants checklist (already-correct, confirm not regressed)

These are scout-verified correct in `release.yml` today. Confirm none regressed during the
flip or the release.

| Invariant | Confirm |
|-----------|---------|
| Exactly 4 publish permissions | The publish job grants ONLY `contents: read`, `packages: write`, `id-token: write`, `attestations: write`. No `contents: write`, no broad scopes. |
| Every third-party `uses:` SHA-pinned | Every `uses:` is a full 40-hex commit SHA (including `reviewdog/action-actionlint`, `sigstore/cosign-installer`, `actions/attest-build-provenance`). |
| Verify by digest, not tag | SBOM, cosign sign, and attest all target `@${{ steps.build.outputs.digest }}`; verification uses `@sha256:<digest>`. |
| Dual SBOM attached | Both SPDX (`spdx-json`) and CycloneDX (`cyclonedx-json`) SBOMs are generated against the digest. |
| Keyless cosign + SLSA provenance | `cosign sign --yes` runs with no `--key` (ephemeral OIDC / Fulcio / Rekor); `actions/attest-build-provenance` binds SLSA provenance to the digest with `push-to-registry: true`. |

`packages: write` is the registry-push permission; confirm it is present and that
`packages` is not granted any wider scope.

## Result recording

When ACC-02 (Steps A to D) and ACC-03 (Steps E to F) all PASS for both images, flip the
matching items in `14-HUMAN-UAT.md` from `result: [pending]` to passed and record the
digests, the `vX.Y.Z` tag, and the run URLs there. The Phase 14 verification stays
`human_needed` until those items are flipped by the operator.

## References

- `.github/workflows/release.yml` (publish job and the verification runbook comment, the
  `cosign verify` plus `gh attestation verify` commands this runbook mirrors).
- `.github/workflows/ci.yml` (the `actionlint` static gate and the seeded allowlist-prep
  comment blocks this flip procedure fills in).
- `cc-worker-config/PRIMING.md` STEP 4 (the H9 five-step homelab gate; ACC-01 lives in
  `14-HUMAN-UAT.md`).
- `14-RESEARCH.md` (the trap table: the exit-0 assertion and the audit-to-block flip).
