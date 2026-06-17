<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 8: Release Hardening (release-please + harden-runner) - Research

**Researched:** 2026-06-15
**Domain:** GitHub Actions CI supply-chain hardening — release automation (release-please) + runner egress hardening (step-security/harden-runner) + SHA-pinning
**Confidence:** HIGH (all action SHAs verified via `git ls-remote` against the live upstream repos; config schemas cited from official docs)

## Summary

This phase is CI-config + docs only. It adds (a) a new `release-please.yml` workflow that, on every push to `main`, maintains an automated release PR (semantic version bump + generated changelog) and tags `v*` on merge, and (b) `step-security/harden-runner` on every job across `ci.yml`, `release.yml`, and the new `release-please.yml`, in `egress-policy: audit` mode. RELX-02 also requires every third-party action across the touched workflows to be pinned to a full commit SHA — which surfaces one real defect in the current tree: the PR-title gate is pinned to the **mutable `v5` major-version tag**, not an immutable release SHA.

The release-please tool is mature and the config shape for this repo's locked decision (`release-type: simple`, single root package `"."`) is small and well-documented. The one genuine subtlety is the **bootstrap**: this is an existing repo with prior tags (`v1.0`, `v1.1`), so the `.release-please-manifest.json` must be seeded with the current version and the config given a `bootstrap-sha` so the first release PR's changelog starts at the right commit rather than walking all history. release-please default tagging includes the `v` prefix, so the tag it cuts (`v1.2.0`) matches the existing `release.yml` `on: push: tags: ['v*']` trigger with no edit and no collision — a clean chain.

**Primary recommendation:** Add `release-please-config.json` + `.release-please-manifest.json` (seeded to `1.2.0`, with `bootstrap-sha` set to the `v1.1` tag commit), a minimal `release-please.yml` (push:main, `contents: write` + `pull-requests: write`, `googleapis/release-please-action` pinned by SHA), a `harden-runner` step (`egress-policy: audit`, SHA-pinned `v2.19.4`) as the **first step of every job** in all three workflows, repin the PR-title gate from the `v5` moving tag to an immutable release SHA, register the two comment-less JSON files in `REUSE.toml`, and document the policy in CONTRIBUTING.md. Validate statically on the dev box with Python `yaml`/`json` parse + `reuse lint`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Automated release PR + version bump | CI / GitHub Actions (`release-please.yml`) | — | Driven by Conventional-Commit history on `main`; lives entirely in the CI tier |
| `v*` tag creation on PR merge | CI / GitHub Actions (release-please action) | — | release-please tags on merge of its own PR; no human/app tagging |
| Image publish on `v*` tag | CI / GitHub Actions (`release.yml`, unchanged) | — | Existing publish job; chains off the tag release-please creates |
| Runner egress restriction | CI / GitHub Actions runner (harden-runner) | — | Network-policy enforcement on the ephemeral runner host; not an app concern |
| Action provenance (SHA pinning) | CI / GitHub Actions (workflow YAML) | — | Supply-chain integrity of the workflow definitions themselves |
| License provenance of comment-less JSON | Repo tooling (`REUSE.toml`) | — | JSON has no comment syntax; REUSE is the established seam (CICD-08) |

No application tier (api/, ui/, cc-worker-config/) is touched this phase.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Release-please configuration**
- **Single root release** (`release-type: simple`, one package `"."`) — keeps the one `v*` version line that already tags v1.0/v1.1/v1.2; NOT per-package independent api/ui versions.
- **Bootstrap** the manifest's last-release version from the latest existing git tag; the first PR bumps from there.
- **New `release-please.yml`** workflow on push-to-`main`. Leave the existing `release.yml` keyed on the `v*` tag release-please creates — clean chain (release-please merges PR → tags `v*` → `release.yml` publish job fires), no trigger collision, no edit to release.yml's trigger.
- **Default changelog sections** (feat → Features, fix → Bug Fixes); `docs`/`chore` hidden — matches the Conventional-Commit PR-title gate already enforced in static-gates.

**Harden-runner egress policy**
- **All jobs hardened:** ci.yml (static-gates, build-scan), release.yml (publish), and the new release-please.yml — every runner gets a `harden-runner` step.
- **`egress-policy: audit` first** (audit-then-block is locked) — baseline the real egress on the first on-runner run, then flip to `block` afterward.
- **Audit-only, no hardcoded allowlist** now; discovering the real endpoints + flipping to `block` with that allowlist is the deferred ACC-02 on-runner step.
- **Document the policy** in a CONTRIBUTING.md release section + an inline comment block in each touched workflow (success criterion 5).
- Every third-party action SHA-pinned, INCLUDING harden-runner, the release-please action, and the existing PR-title gate (`amannn/action-semantic-pull-request`) which currently carries a placeholder SHA + `# TODO pin exact SHA`.

### Claude's Discretion
- Exact release-please action SHA pin, config/manifest JSON field details, and the precise inline-comment wording — at Claude's discretion, grounded in the locked decisions above.

### Deferred Ideas (OUT OF SCOPE)
- Live release-please PR creation + live harden-runner block enforcement + the discovered egress allowlist → deferred **ACC-02** on-runner acceptance (cannot run on the dev box / PR-CI).
- Per-package (api/ui) independent versioning → rejected for v1.2 (single `v*` line kept); revisit only if api and ui need to ship on independent cadences.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RELX-01 | Release automation via release-please — workflow that maintains a release PR (version bump + changelog) from Conventional Commits on main and tags `v*` on merge; config buildable + lintable locally. | Standard Stack (release-please-action v4.4.1 SHA-pinned), Code Examples (config + manifest + workflow), Pitfall 1 (squash-merge), Pitfall 2 (bootstrap on existing repo). First live PR = deferred ACC-02. |
| RELX-02 | CI under harden-runner with audit-then-block egress policy; all third-party actions SHA-pinned; policy documented. | Standard Stack (harden-runner v2.19.4 SHA-pinned), Code Examples (audit step + placement), Pitfall 3 (PR-title gate on mutable `v5` tag), Pitfall 5 (Trivy/Docker egress under audit), Security Domain. First live block-flip = deferred ACC-02. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

From `E:\repos\burrow\CLAUDE.md` and the user-global `CLAUDE.md`:

- **SPDX header on every new/changed headerable file** — two-line header in the file's comment syntax. YAML uses `#`. Comment-less JSON (the two release-please JSON files) is licensed via `REUSE.toml`, NOT an inline header (CICD-08).
- **SHA-pin convention:** every third-party action pinned to a full 40-char commit SHA with a trailing `# vX.Y.Z` comment recording the human-readable version (repo convention, enforced repo-wide).
- **Least-privilege permissions:** `contents: read` is the workflow default; elevate per-job only where required (release-please needs `contents: write` + `pull-requests: write`).
- **Conventional Commits** drive versioning (`feat:`, `fix:`, `docs:`, `chore:`). PR title must itself be a valid Conventional Commit (PRs are squash-merged).
- **No em dashes, no horizontal rules** in authored prose (user-global style); applies to the CONTRIBUTING.md doc additions and inline comment blocks.
- **Security posture v1:** LAN-only, no auth. This phase touches no running-service code paths; the GHCR publish path (`release.yml`) is unchanged.
- **No secrets in the repo.** release-please uses the run's built-in `GITHUB_TOKEN` (no PAT needed for same-repo PRs); do not introduce a stored credential.

## Standard Stack

### Core

| Library / Action | Version | Pin (full SHA) | Purpose | Why Standard |
|------------------|---------|----------------|---------|--------------|
| `googleapis/release-please-action` | v4.4.1 | `5c625bfb5d1ff62eadeeb3772007f7f66fdcf071` | Maintains the automated release PR; tags `v*` on merge | Google-maintained, the de-facto Conventional-Commits release tool; manifest mode is the current (v4) interface `[VERIFIED: git ls-remote googleapis/release-please-action]` |
| `step-security/harden-runner` | v2.19.4 | `9af89fc71515a100421586dfdb3dc9c984fbf411` | Egress monitoring/enforcement on the runner | The standard runner-hardening action; referenced by name in this repo's own `ci-cd-and-testing.md` §5.5 `[VERIFIED: git ls-remote step-security/harden-runner]` |

### Supporting (already in tree, repin only)

| Action | Current pin | Issue | Action required |
|--------|-------------|-------|-----------------|
| `amannn/action-semantic-pull-request` | `e32d7e603df1aa1ba07e981f2a23455dee596825 # v5` | This SHA is the **mutable `v5` major-version tag**, not an immutable release commit. The CONTEXT note "placeholder SHA + `# TODO pin exact SHA`" refers to this. | Repin to an immutable per-release SHA: `0723387faaf9b38adef4775cd42cfd5155ed6017 # v5.5.3` (newest v5 line) `[VERIFIED: git ls-remote amannn/action-semantic-pull-request]` |

**Version-pin decision — release-please-action v4 vs v5:**

A **v5.0.0** of `googleapis/release-please-action` exists (SHA `45996ed1f6d02564a971a2fa1b5860e934307cf7`), released with a "BREAKING CHANGES: upgrade to node24" note `[CITED: github.com/googleapis/release-please-action/releases]`. **Recommendation: pin v4.4.1**, not v5.0.0, because: (1) v5's only documented change is the node24 runtime bump (not a config-schema change), and v4.4.1 is the proven, widely-deployed manifest interface; (2) all official manifest-mode documentation describes the v4 interface; (3) the locked decision references the v4 `release-type: simple` + manifest config shape verbatim. The config files authored here are forward-compatible — a later bump to v5 is a one-line `uses:` SHA change with no config edit. *(This is the planner's call to confirm; both are valid. Logged as A1.)*

**Action-pin decision — amannn v5 vs v6:**

A **v6.x** line exists (newest `v6.1.1` → `48f256284bd46cdaab1048c3721360e808335d50`). **Recommendation: stay on the v5 line** (repin to `v5.5.3`) — v6 is a major bump and the existing gate config works; a major-version migration is out of scope for "pin the existing action to a real SHA." *(Logged as A2.)*

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| release-please | semantic-release | **REJECTED by locked decision.** Do not propose. |
| `release-type: simple` | `release-type: node`/`python` per-package | Rejected — would create independent api/ui version lines; the locked decision keeps one `v*` line. |
| harden-runner audit | harden-runner block (with allowlist) | Block is the **deferred ACC-02** flip; audit-first is locked (cannot discover the real allowlist on the dev box). |

**Installation:** No package install. GitHub Actions are referenced by `uses:` + SHA. No `npm install` runs in this phase. The `release-please` npm engine (latest `17.9.0`, published 2026-06-09 `[VERIFIED: npm view release-please]`) is bundled inside the action; the repo never depends on it directly.

## Package Legitimacy Audit

These are GitHub Actions (referenced by repo + commit SHA), not npm/PyPI/crates packages. The legitimacy gate for Actions is **upstream-repo + immutable-SHA verification**, performed here via `git ls-remote` directly against each canonical upstream repository (the authoritative source — a SHA returned by `ls-remote` provably exists on that repo's tag). slopcheck targets package registries and does not apply to Action refs.

| Action (repo) | Source | Pinned SHA | Tag | Verification | Disposition |
|---------------|--------|-----------|-----|--------------|-------------|
| googleapis/release-please-action | github.com/googleapis/release-please-action | `5c625bfb5d1ff62eadeeb3772007f7f66fdcf071` | v4.4.1 | `git ls-remote` confirmed | Approved |
| step-security/harden-runner | github.com/step-security/harden-runner | `9af89fc71515a100421586dfdb3dc9c984fbf411` | v2.19.4 | `git ls-remote` confirmed | Approved |
| amannn/action-semantic-pull-request | github.com/amannn/action-semantic-pull-request | `0723387faaf9b38adef4775cd42cfd5155ed6017` | v5.5.3 | `git ls-remote` confirmed (replaces mutable `v5` tag pin) | Approved (repin) |

**Packages removed due to slopcheck [SLOP] verdict:** none (no registry packages installed).
**Packages flagged as suspicious [SUS]:** none.

> All three SHAs were resolved live against the canonical upstream repos via `git ls-remote --tags`. A SHA pin to a verified-upstream immutable commit is the supply-chain-correct form; the one defect found was the PR-title gate pinned to a *moving* major-version tag, which RELX-02 fixes.

## Architecture Patterns

### System Architecture Diagram — the release chain

```
   Conventional-Commit PRs merged to main (squash, CC title)
                       │
                       ▼
   ┌─────────────────────────────────────────────┐
   │ release-please.yml   (NEW — on: push: main)  │
   │  job: release-please                          │
   │   step 0: harden-runner (egress: audit)       │
   │   step 1: release-please-action               │
   │     reads CC history since last release       │
   │     ├─ opens/updates a release PR ────────────┼──▶ "chore: release 1.2.0" PR
   │     │   (version bump in manifest +           │     (CHANGELOG.md generated)
   │     │    CHANGELOG.md)                         │
   │     └─ on merge of THAT PR: creates tag v1.2.0 │
   └───────────────────────────────┬───────────────┘
                                   │ git tag v1.2.0 (pushed)
                                   ▼
   ┌─────────────────────────────────────────────┐
   │ release.yml   (EXISTING — on: push: tags v*) │   ◀── trigger UNCHANGED
   │  job: publish (matrix: api, ui)              │
   │   step 0: harden-runner (egress: audit) ◀NEW │
   │   …build → push GHCR → SBOM → cosign → SLSA   │
   └─────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────┐
   │ ci.yml   (EXISTING — on: pull_request, push) │
   │  job static-gates: harden-runner ◀NEW step 0 │
   │  job pr-title:     harden-runner ◀NEW step 0  │  (+ repin amannn SHA)
   │  job build-scan:   harden-runner ◀NEW step 0  │
   └─────────────────────────────────────────────┘
```

The two release workflows chain **via the git tag**, never via a shared file. No edit to `release.yml`'s `on:` trigger is needed or wanted.

### Recommended file layout (repo root + .github/)

```
.github/
└── workflows/
    ├── ci.yml                       # EDIT: harden-runner on all 3 jobs + repin amannn SHA
    ├── release.yml                  # EDIT: harden-runner on publish job (trigger untouched)
    └── release-please.yml           # NEW: push:main → release-please-action
release-please-config.json           # NEW: release-type simple, package "."  (comment-less JSON)
.release-please-manifest.json        # NEW: { ".": "1.2.0" }                    (comment-less JSON)
REUSE.toml                           # EDIT: add the two JSON files above
CONTRIBUTING.md                      # EDIT: add a "Release process & runner hardening" section
docs/ci-cd-and-testing.md            # EDIT (optional): point §6 at the now-concrete release-please config
```

### Pattern 1: Manifest-mode release-please (v4)

**What:** v4 moved per-package config out of action inputs and into two repo-root files. The action takes only `config-file`, `manifest-file`, and a `token`.
**When to use:** Always in v4+. This is the current interface.
**Example:**
```yaml
# Source: github.com/googleapis/release-please-action README (v4 manifest config)
- uses: googleapis/release-please-action@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071 # v4.4.1
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    config-file: release-please-config.json
    manifest-file: .release-please-manifest.json
```

### Pattern 2: harden-runner as the literal first step

**What:** harden-runner installs a network monitor on the runner; it must run **before any other step** so it observes/controls all subsequent egress.
**When to use:** Every job, always step 0 (before even `actions/checkout`).
**Example:**
```yaml
# Source: github.com/step-security/harden-runner README
steps:
  - name: Harden the runner (audit egress)
    uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
    with:
      egress-policy: audit
  - name: Checkout
    uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
  # …rest of job
```

### Anti-Patterns to Avoid

- **Pinning to a major-version tag (`@v5`, `@v4`).** A moving tag can be repointed by the upstream maintainer to any commit — it is not a supply-chain pin. This is exactly the defect in the current PR-title gate. Always pin a full 40-char SHA.
- **harden-runner not first.** If checkout or any network step runs before harden-runner, that egress is unmonitored/uncontrolled. It must be step 0.
- **Editing `release.yml`'s trigger.** The clean chain is tag-based. Adding a `workflow_run` or changing the `on:` trigger reintroduces the collision the locked decision avoids.
- **Seeding the manifest to a wrong/blank version.** On an existing repo, an empty/`0.0.0` manifest makes release-please propose `1.0.0` or walk all history for the changelog. Seed the real current version + `bootstrap-sha`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Version bump from commit history | A custom script parsing `git log` for `feat:`/`fix:` | release-please-action | Conventional-Commit parsing, changelog grouping, PR lifecycle, and tag creation are all solved + battle-tested |
| Changelog generation | A hand-written `CHANGELOG.md` update step | release-please (generates it) | release-please owns the changelog; manual edits fight the tool |
| Runner egress allowlist | iptables/nftables rules in a `run:` step | harden-runner | eBPF-based monitoring, DNS resolution, and the audit→block insights UI are non-trivial to reproduce |
| Knowing the real egress allowlist | Guessing the endpoints now | harden-runner `audit` first, then read the run insights | The locked audit-then-block flow exists precisely because the allowlist is *discovered*, not guessed |

**Key insight:** Every capability this phase needs is a configured action, not authored logic. The "code" is YAML + two small JSON files. The risk is in *configuration correctness* (SHAs, permissions, bootstrap version, step ordering), not implementation.

## Runtime State Inventory

> This is a CI-config phase, not a rename/migration. The relevant "runtime state" is **GitHub-side workflow/release state**, which cannot be exercised on the dev box (it is the deferred ACC-02 on-runner acceptance). Inventoried for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no databases or datastores reference any renamed string. Verified: this phase adds files, renames nothing. | None |
| Live service config | GitHub Actions / release state: release-please reads the merged-release history and the `v*` tags **on the GitHub side**. On first real run it will read the `bootstrap-sha` from config + the manifest version. This is the deferred ACC-02 acceptance — not validatable on the dev box. | Deferred ACC-02 (first on-runner run) |
| OS-registered state | None — no OS-level task/service registration. | None |
| Secrets/env vars | release-please uses the run's built-in `GITHUB_TOKEN` (no new secret). harden-runner needs no secret in audit mode. Verified: no `.env` key added, no new repo secret required. | None |
| Build artifacts | None — no compiled/installed artifact carries a name. The two new JSON files are config, not build output. | None |

**Existing git tags (the bootstrap anchor):** `v1.0` (commit `f5fa388ba23a4617e6b329f24be8672a1aa29c2d`) and `v1.1` (commit `f900a95556d4d82498008a126f3a2cf507e5f3c1`), per `git tag --sort=-v:refname`. Only **two** tags exist; both use the `vMAJOR.MINOR` short form (e.g. `v1.1`, NOT `v1.1.0`). See Pitfall 2 for the bootstrap implication.

## Common Pitfalls

### Pitfall 1: release-please + squash-merge with a Conventional-Commit PR title

**What goes wrong:** A team that squash-merges can break release-please if the squash commit message is not a valid Conventional Commit — release-please reads the **commit messages on `main`**, and a squash collapses a PR into one commit whose message is the PR title.
**Why it happens:** release-please parses `feat:`/`fix:`/etc. from main's commit log. With squash-merge, that log is the sequence of PR titles.
**How to avoid:** This repo **already enforces** a Conventional-Commit PR title via the `pr-title` gate (`amannn/action-semantic-pull-request`) and documents the squash-title rule in `CONTRIBUTING.md` (line 98) and `ci.yml` (lines 109-110). So this repo is **already correctly configured** for release-please-over-squash. Document the linkage in the new CONTRIBUTING section: "the PR-title gate is what makes release-please work under squash-merge." No new config needed.
**Warning signs:** A merged `feat:` PR that produces no version bump → the squash message wasn't Conventional (would have been caught by the gate).

### Pitfall 2: bootstrap on an existing repo with prior tags

**What goes wrong:** With no manifest seed, release-please's first PR proposes `1.0.0` (ignoring the existing `v1.1`) and/or generates a changelog walking the **entire** commit history.
**Why it happens:** release-please tracks "current version" in `.release-please-manifest.json`, not by parsing historical tags. An absent/blank manifest = "no prior release."
**How to avoid (this repo's exact bootstrap):**
1. Seed `.release-please-manifest.json` with the current version. The latest tag is `v1.1`. The current milestone is **v1.2** (REQUIREMENTS.md). Seed the manifest to **`"1.2.0"`** so the next `feat:` produces `v1.3.0` and the next `fix:` produces `v1.2.1` — i.e. release-please continues the line from the v1.2 baseline. *(If the planner instead wants the next release to be exactly v1.2.0, seed `"1.1.0"`; this is a deliberate choice — see A3. Recommendation: seed `"1.2.0"` because the v1.2 milestone work is already merged.)*
2. Set `"bootstrap-sha"` in `release-please-config.json` to the `v1.1` tag commit `f900a95556d4d82498008a126f3a2cf507e5f3c1` so the first release PR's changelog starts **after** v1.1, not at repo genesis. The doc states this setting is "subsequently ignored once release-please has generated at least one release PR" `[CITED: github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md]`.
3. **Tag-format note:** existing tags are `v1.1` (short form). release-please tracks releases via the manifest + its own release PRs, not by parsing the old tag strings, so the non-standard `v1.1` form does **not** break it `[CITED: manifest-releaser.md — "focuses on finding the last merged release PR rather than parsing all historical tags"]`. The first release-please tag will be the standard `v1.2.0`/`v1.3.0` three-part form.
**Warning signs (only visible on the live runner — deferred ACC-02):** first PR titled "chore: release 1.0.0", or a changelog containing every commit since genesis.

### Pitfall 3: the PR-title gate is pinned to a MOVING tag, not a SHA

**What goes wrong:** `ci.yml` line 116 pins `amannn/action-semantic-pull-request@e32d7e603df1aa1ba07e981f2a23455dee596825 # v5`. That SHA **is the `v5` major-version tag** — a tag the maintainer repoints on every v5.x release. It is not an immutable release pin, which is why CONTEXT flags it as the placeholder/`# TODO pin exact SHA` to resolve.
**Why it happens:** `@<sha> # v5` *looks* pinned but the SHA chosen is the floating major tag's current target.
**How to avoid:** Repin to an immutable per-release SHA. Recommended: `0723387faaf9b38adef4775cd42cfd5155ed6017 # v5.5.3` (newest v5-line release) `[VERIFIED: git ls-remote]`. Update the trailing comment to the exact `# v5.5.3` so the convention (SHA + human version) is honest.
**Warning signs:** any `# v<MAJOR>` trailing comment (one number) on a `uses:` line is a moving-tag smell; pins should read `# vX.Y.Z`.

### Pitfall 4: wrong permissions on the release-please job

**What goes wrong:** release-please fails to open the PR or create the tag with an opaque 403.
**Why it happens:** the action needs to write commits/branches (`contents: write`) and open/update a PR (`pull-requests: write`). The repo's least-privilege default is `contents: read`.
**How to avoid:** set job-level `permissions: { contents: write, pull-requests: write }` on the `release-please` job only; keep the workflow-level default at `contents: read`. (The official example also lists `issues: write`; not required for the PR+tag flow, omit it to stay least-privilege — add only if a future label/issue feature is enabled.) `[CITED: github.com/googleapis/release-please-action README]`
**Warning signs (deferred to live run):** "Resource not accessible by integration" on the action step.

### Pitfall 5: harden-runner audit on the build-scan job (Trivy / Docker egress)

**What goes wrong:** none in **audit** mode — audit only *observes* egress, it never blocks. The pitfall is latent and lands at the **deferred block-flip (ACC-02)**: the `build-scan` job pulls base images (`ghcr.io`, `docker.io`/`registry-1.docker.io`, `*.cloudflarestorage.com`), and Trivy downloads its vuln DB (`ghcr.io/aquasecurity/trivy-db`, `mirror.gcr.io`). If block mode ships without those in the allowlist, the build/scan fails.
**Why it happens:** Docker buildx + Trivy have a wide, not-obvious egress surface.
**How to avoid:** **this phase ships audit only** (locked), so nothing breaks now. Document in the workflow comment + CONTRIBUTING that the discovered allowlist (from the audit run's insights) is the input to the deferred block flip, and that `build-scan` will have the widest allowlist of the four jobs. This is exactly why audit-then-block is the locked sequence.
**Warning signs (only at the future block-flip):** "Egress blocked to registry-1.docker.io:443" in the harden-runner step.

### Pitfall 6: SPDX/REUSE on the comment-less JSON files

**What goes wrong:** `reuse lint` goes red because `release-please-config.json` and `.release-please-manifest.json` have no license info (JSON has no comment syntax for an inline header).
**Why it happens:** the SPDX gate (CICD-06) requires every file to declare a license; comment-less files are covered via `REUSE.toml` (CICD-08).
**How to avoid:** add both paths to the existing "Comment-less JSON config" `[[annotations]]` block in `REUSE.toml`. Do **not** add a `// SPDX` line to the JSON (invalid JSON) and do **not** blanket-glob `*.json` (CICD-06 requires a missing inline header on a real source to still surface).
**Warning signs:** `reuse lint` reports the two JSON files under "files without license information."

## Code Examples

> These are the concrete file contents/identifiers the planner turns into task actions. They are intentionally minimal (the locked decision) — not full implementations beyond what the config requires.

### `release-please-config.json` (NEW — comment-less JSON)
```jsonc
// Source: github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md
// (shown with comments for explanation only; the real file is pure JSON)
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "simple",
  "include-v-in-tag": true,
  "bootstrap-sha": "f900a95556d4d82498008a126f3a2cf507e5f3c1",
  "packages": {
    ".": {}
  }
}
```
Notes:
- `release-type: simple` + single package `"."` = the locked single-root release.
- `include-v-in-tag: true` makes the tag `v1.2.0` so it matches `release.yml`'s `tags: ['v*']`. (Default tagging for a root package already includes `v`; stating it explicitly is self-documenting — confirm default with the live run, logged A4.)
- `bootstrap-sha` = the `v1.1` tag commit, so the first changelog starts after v1.1. Ignored after the first release PR.
- Default changelog sections are used (feat→Features, fix→Bug Fixes; docs/chore hidden) by **omitting** a custom `changelog-sections` array — the locked decision is "defaults," so no override is written.
- `$schema` is optional but enables editor/offline validation; harmless to GitHub.

### `.release-please-manifest.json` (NEW — comment-less JSON)
```json
{
  ".": "1.2.0"
}
```
The single key is the root package path; the value is the current released version that the next bump starts from. See Pitfall 2 / A3 for the `1.2.0` vs `1.1.0` seed choice.

### `release-please.yml` (NEW workflow)
```yaml
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Release automation (RELX-01). On every push to main, release-please reads the
# Conventional-Commit history and maintains a release PR (version bump in
# .release-please-manifest.json + generated CHANGELOG.md). Merging that PR tags
# v<X.Y.Z>, which fires release.yml's existing v* publish job — a clean,
# tag-based chain with no trigger edit to release.yml.
#
# Runner hardening (RELX-02): harden-runner runs first in audit mode. The
# discovered egress allowlist + the flip to egress-policy: block is the deferred
# ACC-02 on-runner step. Third-party actions are SHA-pinned; the trailing comment
# records the human-readable version.

name: release-please

on:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  release-please:
    name: Maintain release PR
    runs-on: ubuntu-latest
    # release-please needs to write the release branch/commit and open/update a PR.
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Harden the runner (audit egress)
        uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
        with:
          egress-policy: audit

      - name: Run release-please
        uses: googleapis/release-please-action@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071 # v4.4.1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

### harden-runner step to insert as step 0 of EVERY existing job
Insert this identical block as the first step of: `ci.yml` → `static-gates`, `ci.yml` → `pr-title`, `ci.yml` → `build-scan`, `release.yml` → `publish`.
```yaml
      - name: Harden the runner (audit egress)
        uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
        with:
          egress-policy: audit
```
For `ci.yml`'s `pr-title` job (which currently has only the validation step), harden-runner becomes the new step 0 and the validation step follows.

### `ci.yml` PR-title repin (one-line edit, line 116)
```yaml
# BEFORE (mutable v5 major tag):
        uses: amannn/action-semantic-pull-request@e32d7e603df1aa1ba07e981f2a23455dee596825 # v5
# AFTER (immutable v5.5.3 release SHA):
        uses: amannn/action-semantic-pull-request@0723387faaf9b38adef4775cd42cfd5155ed6017 # v5.5.3
```

### `REUSE.toml` edit (extend the existing comment-less-JSON block)
Add the two paths to the existing `[[annotations]]` block (REUSE.toml lines 21-32):
```toml
path = [
  ".planning/config.json",
  "ui/package.json",
  "ui/tsconfig.json",
  "ui/biome.json",
  "cc-worker-config/plugins/manifest.json",
  "cc-worker-config/plugins/manifest.schema.json",
  "release-please-config.json",
  ".release-please-manifest.json",
]
```

### CONTRIBUTING.md — new "Release process & runner hardening" section (prose identifiers)
A new `## Release process` section documenting: (a) merges to `main` open an automated release PR via release-please; merging it tags `v*` and triggers the GHCR publish; (b) the PR-title gate is what makes this work under squash-merge; (c) CI runs under harden-runner in **audit** mode today, with the egress allowlist + `block` flip tracked as the first on-runner acceptance (ACC-02). No em dashes / no horizontal rules per project style.

### Deferred block-flip allowlist format (DOCUMENT ONLY — do not ship)
For the CONTRIBUTING/inline-comment note describing the deferred ACC-02 flip:
```yaml
# Source: docs.stepsecurity.io — allowed-endpoints is a host:port list, wildcards allowed
- uses: step-security/harden-runner@<sha> # v2.19.4
  with:
    egress-policy: block
    allowed-endpoints: >
      github.com:443
      api.github.com:443
      ghcr.io:443
      registry-1.docker.io:443
```
`[CITED: stepsecurity.io blog — wildcard domains in block mode; format is folded scalar, one host:port per line]`. The **actual** allowlist is discovered from the audit run, not authored now.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| release-please-action v2/v3 with all config as action `with:` inputs | v4 manifest mode: `config-file` + `manifest-file`, config lives in repo-root JSON | v4 (2023) | Config is versioned in-repo, reviewable, and the action surface is tiny `[CITED: release-please-action README]` |
| Pinning actions to `@v4`/`@v5` major tags | Full 40-char commit-SHA pins with `# vX.Y.Z` comment | Industry shift post supply-chain incidents (~2023+); already this repo's convention | A moving tag is not a pin; SHA is the supply-chain control RELX-02 enforces |
| Unrestricted runner egress | harden-runner audit→block egress policy | Standard for security-conscious CI | Runner becomes observable, then lockable, against exfiltration |

**Deprecated/outdated:**
- release-please-action `with:` inputs for `release-type`/`package-name` etc. — deprecated in v4, moved to the config file `[CITED: WebSearch — "in v4, GitHub Actions inputs were deprecated and moved to the config file"]`.
- `release-please-action@v5.0.0` exists (node24) but is newer than the proven manifest interface; v4.4.1 recommended for this phase (see Standard Stack, A1).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pin release-please-action **v4.4.1**, not v5.0.0 (v5's only change is node24; config schema unchanged). | Standard Stack | LOW — if v5 is preferred it's a one-line SHA swap; config files are unchanged. Planner may confirm. |
| A2 | Stay on amannn **v5 line** (repin to v5.5.3), not migrate to v6. | Standard Stack | LOW — v5 gate config works; v6 migration is out of scope for "pin to a real SHA." |
| A3 | Seed `.release-please-manifest.json` to **`1.2.0`** (continue from the already-merged v1.2 baseline), not `1.1.0`. | Pitfall 2 / Code Examples | MEDIUM — wrong seed makes the first auto-version off by a minor. Decide before merge; only visible on the live PR (ACC-02). Recommend `1.2.0`; planner/user should confirm the intended next-release number. |
| A4 | `include-v-in-tag: true` produces `v1.2.0` matching `release.yml`'s `tags: ['v*']`. Default tagging already includes `v`; stated explicitly. | Code Examples | LOW — if the default differed, the explicit key forces `v`; verified only on the live run. |
| A5 | release-please-action accepts the built-in `GITHUB_TOKEN` for same-repo PR + tag creation (no PAT). | Code Examples / Runtime State | LOW — standard for same-repo release-please; a PAT is only needed to trigger downstream workflows from the release PR, which is not required here (the tag, not the PR, triggers release.yml). See Open Question 1. |
| A6 | The deferred block-mode `allowed-endpoints` is a folded-scalar `host:port` list with wildcard support. | Code Examples (deferred) | LOW — documentation-only; the real list is discovered at ACC-02, not shipped now. |

## Open Questions

1. **Does the `v*` tag created by release-please (using `GITHUB_TOKEN`) trigger `release.yml`?**
   - What we know: GitHub deliberately prevents events raised by the **built-in `GITHUB_TOKEN`** from triggering further workflow runs (to avoid recursion). release-please creates the tag as part of merging its PR.
   - What's unclear: whether the `push: tags: ['v*']` event from release-please's tag fires `release.yml`, or is suppressed because it came from `GITHUB_TOKEN`. If suppressed, the documented fix is a PAT/GitHub App token on the release-please action so the tag-push is "human-attributed" and re-triggers workflows.
   - Recommendation: ship with `GITHUB_TOKEN` (locked: no new secret, LAN-only posture) and **flag this as part of the deferred ACC-02 acceptance**: confirm on the first live release whether `release.yml` auto-fires on the release-please tag; if not, the remediation (a scoped GitHub App token for release-please, or manually re-running release.yml on the tag) is an ACC-02 follow-up, not a dev-box-blockable item. Document this caveat in the CONTRIBUTING release section so the first releaser knows to check. *(This is the single most important thing to verify on the first live run.)*

2. **Seed value `1.2.0` vs `1.1.0`** — see A3. Needs a human decision on what the next auto-cut release number should be. Does not block authoring (the file is trivially editable); just must be correct before the first real merge.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (`yaml`, `json`) | Static YAML/JSON parse on dev box | ✓ (assumed present — repo uses uv/Python 3.12) | 3.12 | `python -c "import yaml,json"` |
| `reuse` (via `uvx --with charset-normalizer`) | SPDX/REUSE lint of the two JSON files | ✓ (already used in `ci.yml` spdx step) | per uvx | none needed |
| `actionlint` | Workflow schema lint | ✗ (CONTEXT: "actionlint may be unavailable" on Windows dev host) | — | Python YAML parse for structural validity; full action-schema lint is the first CI run (ACC-02-adjacent) |
| GitHub Actions runner | Live release-please PR + harden-runner enforcement | ✗ (dev box) | — | Deferred ACC-02 on-runner acceptance (by design) |
| `git` | Read existing tags for bootstrap-sha | ✓ | — | confirmed: `git tag` returns `v1.0`, `v1.1` |

**Missing dependencies with no fallback:** GitHub Actions runner — the live release-please PR and live harden-runner behavior are **deferred ACC-02 by design**, not a blocker for this phase's CI-config + docs deliverable.
**Missing dependencies with fallback:** `actionlint` — use Python `yaml` parse for structural validity; the authoritative workflow-schema check is the first push to a runner.

## Validation Architecture

> `nyquist_validation` is enabled (config.json `workflow.nyquist_validation: true`). This phase ships no test framework code (no api/ui change); validation is **static-parse + lint** of the authored YAML/JSON + the existing SPDX gate.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None new. Validation = Python stdlib `yaml`/`json` parse + `reuse lint` (existing CICD-06 gate) |
| Config file | none — see Wave 0 |
| Quick run command | `python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/release-please.yml .github/workflows/ci.yml .github/workflows/release.yml` |
| Full suite command | `python -c "import json; json.load(open('release-please-config.json')); json.load(open('.release-please-manifest.json'))" && uvx --with charset-normalizer reuse lint` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command (dev-box-runnable) | File Exists? |
|--------|----------|-----------|--------------------------------------|-------------|
| RELX-01 | `release-please.yml` is valid YAML with the right trigger/permissions | static-parse | `python -c "import yaml; d=yaml.safe_load(open('.github/workflows/release-please.yml')); assert 'main' in d['on']['push']['branches']; assert d['jobs']['release-please']['permissions']=={'contents':'write','pull-requests':'write'}"` | ❌ Wave 0 (file is new) |
| RELX-01 | `release-please-config.json` parses + has `release-type: simple` + package `"."` | static-parse | `python -c "import json; c=json.load(open('release-please-config.json')); assert c['release-type']=='simple'; assert '.' in c['packages']"` | ❌ Wave 0 |
| RELX-01 | `.release-please-manifest.json` parses + seeds the root version | static-parse | `python -c "import json; m=json.load(open('.release-please-manifest.json')); assert m['.']"` | ❌ Wave 0 |
| RELX-02 | harden-runner present as step 0 of every job in all 3 workflows | static-parse | `python` assertion: for each job, `jobs[j]['steps'][0]['uses'].startswith('step-security/harden-runner@')` and `steps[0]['with']['egress-policy']=='audit'` | ❌ Wave 0 |
| RELX-02 | Every `uses:` is pinned to a 40-char SHA (no `@vN` floating tags) | static-parse | regex over the three workflow files: every `uses:` ref after `@` is `[0-9a-f]{40}` | ❌ Wave 0 |
| RELX-02 | PR-title gate repinned off the moving `v5` tag | static-parse | assert the amannn `uses:` SHA == `0723387…` (not `e32d7e60…`) | ❌ Wave 0 |
| RELX-01/02 | SPDX/REUSE green incl. the two new JSON files | lint | `uvx --with charset-normalizer reuse lint` | ✓ (gate exists; REUSE.toml needs the two new paths) |

### Sampling Rate
- **Per task commit:** the relevant static-parse one-liner for the file just authored (YAML parse / JSON parse / SHA-pin regex).
- **Per wave merge:** all three workflow YAML parse + both JSON parse + `reuse lint`.
- **Phase gate:** full static suite green + `reuse lint` green before `/gsd:verify-work`. (Live behavior is the deferred ACC-02 on-runner acceptance, explicitly NOT a PR-CI command.)

### Wave 0 Gaps
- [ ] A small dev-box validation script (or inline commands in the plan) asserting: every `uses:` in the three workflows is a 40-hex SHA; harden-runner is step 0 of every job with `egress-policy: audit`; the two JSON files parse and carry the locked keys. (No test *framework* needed — pure `python -c`/`yaml`/`json`.)
- [ ] No `conftest.py`/fixtures needed (no pytest surface this phase).
- [ ] Framework install: none.

*(There is no application-code test surface this phase; the "tests" are static parse/lint assertions runnable on the Windows dev box, matching the locked constraint "statically validatable.")*

## Security Domain

> `security_enforcement: true`, ASVS level 1 (config.json). This phase is itself a **security-hardening** phase; the relevant controls are supply-chain (V14 / SLSA-adjacent), not app-runtime auth.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface (v1 LAN-only; CI uses built-in `GITHUB_TOKEN`) |
| V3 Session Management | no | n/a |
| V4 Access Control | yes (CI scope) | Least-privilege workflow permissions: `contents: read` default; per-job elevation only (release-please `contents: write` + `pull-requests: write`) |
| V5 Input Validation | no (no user input path) | Static YAML/JSON parse is the only "validation"; no runtime input |
| V6 Cryptography | no (this phase) | Image signing/provenance lives in `release.yml` (unchanged); not re-implemented here |
| V14 Config & Supply Chain | **yes (primary)** | SHA-pin every third-party action; harden-runner egress policy; least-privilege tokens; no stored secret |

### Known Threat Patterns for GitHub Actions CI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Compromised/repointed third-party action (mutable tag) | Tampering / Elevation | Full 40-char SHA pin (RELX-02). The current `amannn@v5` moving-tag pin is the live instance of this risk — repin to an immutable SHA. |
| Data exfiltration from the runner (malicious dependency phoning home) | Information Disclosure | harden-runner egress policy: audit now (observe), block later (deny non-allowlisted egress) — the locked audit-then-block flow |
| Over-privileged `GITHUB_TOKEN` (a malicious action escalating) | Elevation of Privilege | `contents: read` default + minimal per-job elevation; release-please gets exactly `contents: write` + `pull-requests: write`, nothing broader |
| Secret leakage via PR from a fork | Information Disclosure | Unchanged from existing posture: publish credentials live only in `release.yml` (tag-triggered, never on fork PRs); release-please uses only `GITHUB_TOKEN` |
| Supply-chain tampering of release artifacts | Tampering | Already covered by `release.yml` (cosign keyless + SLSA provenance); this phase preserves that chain by triggering it via the release-please tag |

## Sources

### Primary (HIGH confidence)
- `git ls-remote --tags` against `github.com/googleapis/release-please-action`, `github.com/step-security/harden-runner`, `github.com/amannn/action-semantic-pull-request` — **all three action SHAs verified directly against upstream** (the authoritative pin source).
- `npm view release-please version` → `17.9.0` (modified 2026-06-09) — the engine version, confirms the tool is actively maintained.
- `git tag --sort=-v:refname` (this repo) → `v1.1`, `v1.0` + their commit SHAs — the bootstrap anchor.
- Local file reads: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `REUSE.toml`, `CONTRIBUTING.md`, `REQUIREMENTS.md`, `STATE.md`, `08-CONTEXT.md`, `config.json`.
- github.com/googleapis/release-please-action README — v4 manifest inputs, permissions, minimal config/manifest.
- github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md — bootstrapping, `bootstrap-sha`, "finds the last merged release PR not historical tags."
- github.com/step-security/harden-runner README — `egress-policy: audit` step shape, first-step requirement, Windows/macOS audit-only note.

### Secondary (MEDIUM confidence)
- WebFetch of github.com/googleapis/release-please-action/releases — v5.0.0 (node24 breaking) + v4.4.1 / v4.4.0 SHAs (cross-checked against `git ls-remote`, which is the authority).
- stepsecurity.io blog "wildcard domains in block mode" + WebSearch — `allowed-endpoints` host:port folded-scalar format with wildcard support (used only for the deferred-flip documentation note).

### Tertiary (LOW confidence)
- WebFetch of release-please customizing.md returned partial/404 content for the `include-v-in-tag` default — the explicit `include-v-in-tag: true` in the config sidesteps any default ambiguity (A4).

## Metadata

**Confidence breakdown:**
- Standard stack (action SHAs/versions): **HIGH** — every SHA verified via `git ls-remote` against the canonical upstream repo, not just a registry/web claim.
- Architecture (the tag-based chain, manifest config shape): **HIGH** — config shape cited from official docs; the chain is the locked decision and the existing `release.yml` trigger is read from the file.
- Bootstrap mechanics: **HIGH** for the mechanism (cited), **MEDIUM** for the exact seed value (`1.2.0` vs `1.1.0` is a product decision — A3).
- Pitfalls: **HIGH** — squash/CC and SHA-pin pitfalls verified against the actual repo files; the `GITHUB_TOKEN`-doesn't-retrigger caveat is a known GitHub behavior surfaced as Open Question 1 for the live run.
- Live behavior (release PR creation, harden-runner enforcement, tag-retrigger): **deferred ACC-02 by design** — not validatable on the dev box.

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable; action SHAs are immutable. Re-verify only if the planner chooses to bump release-please-action to v5 or amannn to v6.)
