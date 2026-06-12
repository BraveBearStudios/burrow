<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Deferred Items — Phase 02

Out-of-scope discoveries logged during execution (per the executor scope-boundary
rule). These are NOT fixed by the current plan.

| Found During | Item | Why Deferred |
|--------------|------|--------------|
| 02-01 Task 2 | `.planning/ROADMAP.md.tmp` is a stray, SPDX-non-compliant temp file (present before this plan started; created 2026-06-10 13:46) — the only file failing the full-repo `reuse lint` (165/166 compliant). | Pre-existing artifact unrelated to this plan's files; not created or touched by 02-01. Likely a leftover from a prior `roadmap.update-*` SDK run. Should be removed by whoever owns the ROADMAP write path; out of scope for the terminal-bridge plan. All 02-01 files pass `reuse lint-file` (exit 0). |
