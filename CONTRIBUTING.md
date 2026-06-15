<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Contributing to Burrow

Thanks for your interest in contributing. This document covers the license, the
Contributor License Agreement (CLA), and the mechanics of submitting changes.

## License

Burrow is licensed under the **GNU Affero General Public License v3.0 or later**
(`AGPL-3.0-or-later`). By contributing, you agree that your contributions are
licensed to everyone under the same AGPL-3.0-or-later terms, and you grant Brave
Bear Studios the additional rights described in the CLA below.

What AGPL means in practice, and why it was chosen:

- Anyone may use, study, modify, and redistribute Burrow.
- Anyone who distributes Burrow, **or runs a modified version as a network
  service**, must make the complete corresponding source of their version
  available under the AGPL (section 13 — the "network use is distribution"
  clause). This is what prevents Burrow from being taken closed-source or run as
  a closed hosted service.

## Contributor License Agreement (CLA)

Before your first contribution can be merged, you must agree to the project CLA.
The CLA does **not** take your copyright away — you keep it. It grants Brave Bear
Studios a broad, irrevocable license to use your contribution, including the
right to relicense it (for example, in a separately licensed commercial edition).
This lets the project sustain a commercial offering without any contributor
losing rights to their own work.

- Individual contributors: read and agree to [`CLA/cla-individual.md`](CLA/cla-individual.md).
- Contributing on behalf of a company: have an authorized signer agree to
  [`CLA/cla-entity.md`](CLA/cla-entity.md), which also authorizes the named
  employees to contribute.

**How to record agreement.** Until an automated CLA bot is wired up, indicate
agreement by adding a `Signed-off-by` trailer to every commit (see DCO-style
sign-off below) **and**, on your first pull request, a comment stating:

> I have read and agree to the Burrow Contributor License Agreement
> (CLA/cla-individual.md), version 1.0.

Sign off each commit with:

```
git commit -s -m "feat: add the thing"
```

which appends `Signed-off-by: Your Name <you@example.com>`. The sign-off
certifies the Developer Certificate of Origin (https://developercertificate.org/)
**and**, together with your PR statement, your agreement to the CLA.

## SPDX headers

Every source file carries a two-line SPDX header so license provenance is
machine-checkable and survives file moves. Use the comment syntax for the
language:

```python
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
```

```typescript
// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later
```

```html
<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
```

Keep the copyright line as `Brave Bear Studios` for project-authored files. If a
file is substantially your original contribution and you wish to be credited,
you may add a second `SPDX-FileCopyrightText` line with your name — your
underlying copyright is unaffected by the CLA.

## Submitting changes

1. Fork and branch from `main`. Branch naming: `{type}/{short-description}`
   (e.g. `feat/terminal-reconnect`, `fix/vmid-race`).
2. Follow the conventions in `CLAUDE.md` and the tech spec
   (`docs/tech-spec.md`): `/api/v1` routes, the standard response
   envelope, snake_case DB columns, structured logging, security headers, tests
   with every change.
3. Use **Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:` …) — commit
   messages drive versioning.
4. Open a pull request. Requirements: CLA agreed, all CI checks green, at least
   one maintainer review. PRs are squash-merged; the PR title becomes the squash
   commit and must itself be a valid Conventional Commit.

## Release process

Releases are automated by **release-please** and chained to the GHCR publish by a
tag.

**The release chain.** A merge to `main` opens (or updates) an automated release
pull request via release-please. That PR bumps the version in
`.release-please-manifest.json` and regenerates `CHANGELOG.md` from the
Conventional-Commit history on `main`. Merging the release PR tags a `v*`
release, and the `v*` tag fires the GHCR publish job in `release.yml`. The two
workflows never share a file or edit each other's trigger: the chain is purely
tag-based.

**Why the PR-title gate matters here.** Because PRs are squash-merged, the squash
commit message is the PR title (see `## Submitting changes`). release-please reads
those Conventional-Commit messages on `main` to compute the next version bump, so
the PR-title gate is what makes the automated versioning work. A non-conforming
title would either block the merge or be invisible to the bump calculation.

**Runner hardening (audit today, block later).** Every CI job runs under
`step-security/harden-runner` in `egress-policy: audit` mode (all four runners
across `ci.yml`, `release.yml`, and `release-please.yml`). Audit mode only
observes egress, so it breaks nothing today. Turning the discovered egress into an
`allowed-endpoints` allowlist and flipping `egress-policy: block` is the first
on-runner acceptance step (deferred ACC-02), and it must wait for real audit
telemetry from a live runner. The `build-scan` and `publish` jobs will need the
widest allowlist because of their Docker, Trivy, and GHCR egress.

**First-release caveat (`GITHUB_TOKEN` retrigger).** release-please tags the
release with the run's built-in `GITHUB_TOKEN`. GitHub suppresses workflow events
raised by `GITHUB_TOKEN` to avoid recursive runs, so the new `v*` tag may not
auto-trigger `release.yml`. The first releaser must confirm that `release.yml`
actually fires on the release-please tag. If it does not, the remediation is an
ACC-02 follow-up: either run the release-please action with a scoped GitHub App
token, or manually re-run `release.yml` on the tag.

## Architecture decisions

Anything that deviates from the baseline architecture needs an ADR in
`docs/adr/` before merge. See the spec's ADR backlog. Don't silently deviate.

## Reporting security issues

Please do not open public issues for security vulnerabilities. See
`SECURITY.md` for private disclosure (or email the maintainers) so a fix can ship
before details are public.
