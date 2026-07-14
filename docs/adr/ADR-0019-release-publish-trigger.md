<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0019: Release publish trigger (workflow_dispatch escape hatch)

## Status

Accepted (v1.4, Phase 20 / ACC-06). Supersedes the assumption in ADR-0008-era
release wiring that a release-please tag alone would fire `release.yml`.

## Context

`release.yml` (the sign + attest + GHCR-publish supply chain) triggered only on
`push: tags: v[0-9]+.[0-9]+.[0-9]+` and `release: published`. release-please
(`release-please.yml`) creates the version tag + GitHub Release using the run's
built-in `GITHUB_TOKEN`.

GitHub **suppresses workflow triggers for events created by `GITHUB_TOKEN`** (an
anti-recursion protection). So when release-please tagged `v1.4.0`, neither
`push: tags` nor `release: published` fired `release.yml` — the signing pipeline
never ran. `release-please.yml` had documented the risk in a comment, but the
first real release confirmed it live.

Two repo policies then blocked the obvious manual recovery:
- **Immutable releases** — the `v1.4.0` Release object could not be recreated
  after deletion (`HTTP 422: tag_name was used by an immutable release`).
- A tag **creation-restriction** rule — a user `git push` of the `v1.4.0` tag was
  rejected (`GH013 ... creations being restricted`); only the release-please
  app/`GITHUB_TOKEN` may create `v*` tags.

Net: `v1.4.0` was consumed with no signed artifacts, and the pipeline as wired
could not produce a signed release at all.

## Decision

Add a manual **`workflow_dispatch`** trigger to `release.yml` as the escape hatch:

- inputs: `version` (semver, e.g. `1.4.1`) and `ref` (git ref/SHA, default `main`).
- a `Resolve release version` step derives the version from EITHER the tag
  (`github.ref_name` minus the leading `v`) OR the dispatch input, failing closed
  if it is not semver `X.Y.Z`, so both trigger paths share one version source.
- checkout honors the `ref` input; `docker/metadata-action` tags off the resolved
  version, so a dispatch produces byte-identical tags/labels to a real tag push.

The `push: tags` + `release: published` triggers are unchanged (they will work if
the token limitation is ever removed). The operator dispatches the signed publish
on demand after release-please cuts each tag.

## Consequences

- The v1 **no-stored-secret** posture is preserved (no PAT, no GitHub App secret).
- Each release adds one manual `gh workflow run release.yml -f version=X.Y.Z` step.
- `v1.4.0` is permanently burned; the first signed release is **`v1.4.1`**,
  published via dispatch (ACC-06 met: run `29355954285`, both images built, dual
  SBOMs, cosign keyless signature, SLSA build-provenance attestation, all green).
- A dispatched version does not auto-create a matching GitHub Release object; the
  GHCR image tags + signatures + attestations are the supply-chain deliverable, so
  this is acceptable. release-please can still open a Release PR for changelog/tag
  bookkeeping; its tag would simply be signed by a follow-up dispatch.

## Alternatives considered

- **release-please with a PAT / GitHub App token** — its tag creation would then be
  user-attributed and auto-fire `release.yml`. Rejected for v1: it introduces a
  stored secret (breaks the no-stored-secret posture) and the token's actor must be
  granted a bypass of the tag creation-restriction. Reconsider if the manual
  dispatch becomes a burden (would warrant its own ADR + secret management).
- **`release: published` only** — same `GITHUB_TOKEN` suppression; no improvement.
- **`repository_dispatch` from the release-please job** — possible, but couples the
  two workflows and still runs under `GITHUB_TOKEN`; more moving parts than a
  human-triggered dispatch.

## Follow-ups

- Flip harden-runner egress `audit -> block` on `release.yml` from run
  `29355954285`'s Step-Security insights (ACC-06 item 14). The build egress
  includes base-image pulls + PyPI (the Dockerfile.api pip upgrade) + npm beyond
  the cosign/OIDC/GHCR set, so the allowlist must come from the real audit, not a
  guess.
- Independent `cosign verify` + `gh attestation verify` against the published
  digests (operator; needs registry read auth + `cosign`) — also re-verified live
  in Phase 22 (ACC-05) against a homelab-pulled image.
