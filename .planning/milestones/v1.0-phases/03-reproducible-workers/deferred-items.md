<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 03 — Deferred / Out-of-Scope Items

Items discovered during execution that are outside the current task's change set.
Logged per the executor scope boundary; NOT fixed in this plan.

## Pre-existing REUSE non-compliance on planning docs (discovered Plan 03-02)

`uvx reuse lint` reports 4 files missing copyright/license info:

- `.planning/phases/03-reproducible-workers/03-01-PLAN.md`
- `.planning/phases/03-reproducible-workers/03-02-PLAN.md`
- `.planning/phases/03-reproducible-workers/03-03-PLAN.md`
- `.planning/phases/03-reproducible-workers/03-VALIDATION.md`

These are GSD planning artifacts authored without the inline SPDX two-line header.
They are not source files in any test tier and are unrelated to the Plan 03-02
change set (manifest + boot manifest processing). The two JSON files this plan adds
(`manifest.json`, `manifest.schema.json`) ARE covered via the `REUSE.toml`
`[[annotations]]` block and are NOT in the missing list.

Resolution: add the inline header (or a `REUSE.toml` annotation for the
`.planning/phases/**` planning docs) in a docs/CI plan (e.g. 03-03 CI wiring),
not here. Tracked so the verifier does not attribute this to Plan 03-02.
