<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: partial
phase: 04-hardening-release
source: [04-VERIFICATION.md]
started: 2026-06-11T00:00:00Z
updated: 2026-06-11T00:00:00Z
---

> **Superseded by v1.3 Phase 14.** These pending real-infra and CD items are rolled up into and
> superseded by `.planning/phases/14-first-real-infra-acceptance/14-HUMAN-UAT.md` (the v1.3
> Phase 14 consolidated real-infra acceptance gate). Run them from the Phase 14 checklist;
> the items below are preserved for history and their results are unchanged.

## Current Test

[awaiting dev-homelab smoke (real Proxmox) + first CI run + a real GHCR release]

## Tests

All CI-provable must-haves pass in code/tests (api 173, ui 96, reuse 275/275). These 5 are
the real-infrastructure / CD acceptances the ROADMAP designates as the dev-homelab smoke and
first-CI-run authority, not hermetic CI failures.

1. **Reaper destroys a real injected orphan LXC + frees its VMID (on its actual node)** (CAP-03).
   Inject an orphan CT in the worker pool on a non-default node, run a reconcile pass, confirm it
   is destroyed on the correct node and the VMID freed; out-of-pool CTs untouched. (CR-01 fix:
   `listManagedCts()` returns (node, vmid); verify the real Proxmox path matches the Fake model.)
   - Status: ⬜ pending

2. **Idle workspace auto-stops after the real window** (CAP-02). Boot a workspace, disconnect the
   terminal, wait `idle_window_s`, confirm auto-stop emits `workspace.stopped` with `reason: idle`;
   a brief reconnect does NOT trip it.
   - Status: ⬜ pending

3. **Capacity holds under real concurrent creates** (CAP-02). Fire concurrent creates near the
   node-RAM threshold; confirm no overcommit (the atomic check+reserve lock holds on real metrics).
   - Status: ⬜ pending

4. **Image build + Trivy run on the GitHub runner** (CICD-04). First CI run is the authority:
   both images build (digest-pinned, non-root, HEALTHCHECK `/api/v1/health`), Trivy fails the build
   on HIGH/CRITICAL, SARIF uploads. (Docker/Buildx unavailable on the Windows dev host.)
   - Status: ⬜ pending

5. **Real GHCR publish + signature/provenance verify** (CICD-05). Tag `v*`/publish a release; confirm
   the images land in GHCR by digest, `cosign verify` (keyless/OIDC) passes, and
   `gh attestation verify` confirms the SLSA provenance + dual SBOM are attached.
   - Status: ⬜ pending

## Advisory UI follow-ups (non-blocking, from 04-UI-REVIEW.md, 22/24)

- Activity drawer responsive width: implement the phone full-width sheet (criterion 10); currently a
  single `min(360px, 100vw)` constant with no breakpoint.
- Restore the spec's `--accent-line` `:focus-visible` ring + custom scrollbar (the `<aside>` sets
  `outline:none` with no replacement focus indicator: a minor a11y gap).

## Notes

- CI-provable contract: PASSED. Consistent with the Phase 2/3 closeout pattern (`human_needed: real-* deferred`).
- When the homelab smoke + first CI run + a real release pass, flip each item to ✅ and set
  04-VERIFICATION.md `status: passed`.
