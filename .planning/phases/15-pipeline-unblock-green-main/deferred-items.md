# Phase 15 — Deferred / Out-of-Scope Items

Discoveries made during execution that are outside the current plan's scope. Logged
per the GSD scope boundary (auto-fix only issues directly caused by the current
task's changes; log the rest here for the owner to decide).

## D-15-02-01 — reuse lint invalid SPDX expression in 15-02-PLAN.md (CICD-06, not RELX-05) — **RESOLVED 2026-07-13**

**Resolution:** Fixed in the Phase 15 closeout (a green-main blocker for the phase goal). Bracketed the quoted two-line SPDX header in `15-02-PLAN.md` with the `REUSE-IgnoreStart` / `REUSE-IgnoreEnd` comment pair (reuse's documented mechanism). `uvx --with charset-normalizer reuse lint` now returns exit 0 — "compliant... 464/464, 0 Invalid SPDX License Expressions." Original report retained below.


- **Found during:** Plan 15-02 Task 1 (running `uvx --with charset-normalizer reuse lint`,
  the ci.yml hard gate, to confirm the new `.trivyignore` was recognized).
- **Symptom:** `reuse lint` exits non-zero with `Invalid SPDX License Expressions: 1`.
  Files with copyright/license info are 460/460 (the new `.trivyignore` is clean and
  recognized via its inline `#` header). The single offending file is
  `.planning/phases/15-pipeline-unblock-green-main/15-02-PLAN.md`.
- **Root cause:** the plan's own action prose quotes the two-line SPDX header inline, and
  the license-identifier tag is followed by other text on the SAME line
  (`... AGPL-3.0-or-later`), followed by a policy comment block documenting ...`). reuse
  parses everything after the tag on that line as a license expression, which does not
  parse. It is the only such occurrence in the repo (other planning docs put the tag on
  its own line, which parses as a valid expression).
- **Why deferred:** not caused by this task's changes (the committed plan artifact predates
  execution) and it is a CICD-06 / SPDX-gate concern, not RELX-05 (the Trivy gate). Editing
  a committed plan spec during execution is out of scope. My `.trivyignore` obligation
  (recognized, does not red the gate on the new file) is independently satisfied.
- **Impact:** the repo-wide reuse hard gate in ci.yml will red on the branch / PR #3 CI
  until this is fixed. This is a "green main" blocker owned by the green-main sequencing
  (Phase 16 merges PR #3 onto green main), NOT by RELX-05.
- **Exact remedy (one line, tool-sanctioned):** either reword the plan sentence so the
  license-identifier tag is not followed by other text on the same line, or bracket the
  quoted header block with the reuse ignore comment pair (reuse's documented mechanism for
  text that is not a real license expression). Confirm with
  `uvx --with charset-normalizer reuse lint` returning exit 0.
