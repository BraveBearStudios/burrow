<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 8: Release Hardening (release-please + harden-runner) - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — 2 grey areas proposed, both accepted as recommended

<domain>
## Phase Boundary

CI-config + docs only (`.github/workflows/` + `docs/`), dev-box-buildable and statically
validatable (YAML/JSON parse + `reuse lint`). Two locked requirements:

- **RELX-01 (release automation):** a `release-please` workflow that, from Conventional
  Commits on `main`, maintains a release PR (semantic version bump + generated changelog)
  and tags `v*` on merge. release-please is LOCKED — do not propose semantic-release.
- **RELX-02 (runner hardening):** CI workflows run under `step-security/harden-runner` with
  an egress allowlist using an **audit-then-block** policy, and every third-party action
  across the touched workflows pinned to a full commit SHA (incl. harden-runner and the
  release-please action), SHA-pin convention preserved repo-wide. Policy documented.

The live release-please PR and live harden-runner enforcement are the deferred **ACC-02**
on-runner acceptance, NOT a PR-CI command. No React app or API code is touched.

</domain>

<decisions>
## Implementation Decisions

### Release-please Configuration
- **Single root release** (`release-type: simple`, one package `"."`) — keeps the one `v*`
  version line that already tags v1.0/v1.1/v1.2; NOT per-package independent api/ui versions.
- **Bootstrap** the manifest's last-release version from the latest existing git tag
  (inspect `git tag` during planning); the first PR bumps from there.
- **New `release-please.yml`** workflow on push-to-`main`. Leave the existing `release.yml`
  keyed on the `v*` tag release-please creates — clean chain (release-please merges PR →
  tags `v*` → `release.yml` publish job fires), no trigger collision, no edit to release.yml's trigger.
- **Default changelog sections** (feat → Features, fix → Bug Fixes); `docs`/`chore` hidden —
  matches the Conventional-Commit PR-title gate already enforced in static-gates.

### Harden-runner Egress Policy
- **All jobs hardened:** ci.yml (static-gates, build-scan), release.yml (publish), and the
  new release-please.yml — every runner gets a `harden-runner` step.
- **`egress-policy: audit` first** (audit-then-block is locked) — baseline the real egress on
  the first on-runner run, then flip to `block` afterward.
- **Audit-only, no hardcoded allowlist** now; discovering the real endpoints + flipping to
  `block` with that allowlist is the deferred ACC-02 on-runner step.
- **Document the policy** in a CONTRIBUTING.md release section + an inline comment block in
  each touched workflow (success criterion 5).

### Claude's Discretion
- Exact release-please action SHA pin, config/manifest JSON field details, and the precise
  inline-comment wording — at Claude's discretion, grounded in the locked decisions above.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml` — existing static-gates + build-scan jobs; third-party actions
  already SHA-pinned (checkout v4.3.1, setup-uv v6.8.0, setup-node v4.4.0, Trivy actions).
  PR-title gate via `amannn/action-semantic-pull-request` carries a placeholder SHA + a
  `# TODO pin exact SHA` — Phase 8 RELX-02 must resolve this to a real SHA.
- `.github/workflows/release.yml` — existing `v*`-tag-triggered publish job (two-image GHCR
  matrix + dual SBOM + keyless cosign + SLSA attestation), all 5 actions real-SHA-pinned.
  harden-runner was intentionally deferred here (v1.0 Plan 04-05 note) → added this phase.
- `REUSE.toml` — licenses non-headerable files repo-wide; new release-please JSON config
  (comment-less) is licensed via this path per CICD-08, not an inline header.

### Established Patterns
- All third-party actions SHA-pinned with a trailing `# vX.Y.Z` comment (repo convention).
- `contents: read` least-privilege default on jobs; elevate per-job only where required
  (release-please needs `contents: write` + `pull-requests: write`).
- SPDX header on every headerable source file; comment-less JSON covered by REUSE.toml.

### Integration Points
- release-please.yml (new, push:main) → creates the `v*` tag → existing release.yml publish
  job (v*-tag trigger, unchanged) fires. The two workflows chain via the tag, not a shared file.
- harden-runner added as the first step of every job in all three workflows.

</code_context>

<specifics>
## Specific Ideas

- Audit-then-block is explicitly start-in-audit: ship `egress-policy: audit` this phase; the
  flip to `block` + the discovered allowlist is deferred ACC-02 (first on-runner enforcement).
- The PR-title gate's placeholder `amannn/action-semantic-pull-request` SHA must be pinned to
  a real commit SHA as part of "every third-party action SHA-pinned" (criterion 4).

</specifics>

<deferred>
## Deferred Ideas

- Live release-please PR creation + live harden-runner block enforcement + the discovered
  egress allowlist → deferred ACC-02 on-runner acceptance (cannot run on the dev box / PR-CI).
- Per-package (api/ui) independent versioning → rejected for v1.2 (single `v*` line kept);
  revisit only if api and ui need to ship on independent cadences.

</deferred>
