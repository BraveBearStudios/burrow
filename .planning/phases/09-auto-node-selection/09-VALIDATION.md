---
phase: 9
slug: auto-node-selection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Backend pytest (unit + integration over the Fake's multi-node capacity) + UI vitest for the
> modal Auto option. Real multi-node Proxmox is the deferred ACC-01 dev-homelab smoke (by design).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (api: `tests/unit` + `tests/integration`) + vitest/MSW (ui) — both already in tree |
| **Config file** | `api/pyproject.toml` (pytest) · `ui/vitest.config.ts` |
| **Quick run command** | `cd api && python -m pytest tests/unit/test_node_selection.py -q` |
| **Full suite command** | `cd api && python -m pytest -q && cd ../ui && npx vitest run` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick command (the new node-selection unit tests)
- **After every plan wave:** Run the full api suite (+ ui vitest if the modal changed)
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | WSX-01 | Fake supports per-node fractions (backward-compat float) | unit | `python -m pytest tests/unit/test_fake_node_fractions.py -q` | ❌ W0 | ⬜ pending |
| 9-01-02 | 01 | 1 | WSX-01 | `worker_nodes` Settings + shared `_fits` helper (strict >, == allowed) | unit | `python -m pytest tests/unit/test_node_capacity_helper.py -q` | ❌ W0 | ⬜ pending |
| 9-02-01 | 02 | 2 | WSX-01 | `selectNode` picks least-loaded-fitting; over-threshold skipped; boundary eligible; tie→name asc; no-fit→CapacityError | unit | `python -m pytest tests/unit/test_node_selection.py -q` | ❌ W0 | ⬜ pending |
| 9-02-02 | 02 | 2 | WSX-01 | selection runs inside `_create_lock`; manual pick unchanged; seam-leakage green | unit+integration | `python -m pytest tests/unit/test_seam_leakage.py tests/integration/test_create_auto_node.py -q` | ❌ W0 | ⬜ pending |
| 9-02-03 | 02 | 2 | WSX-01 | `WorkspaceCreate.node` Optional=None signals auto; `/nodes` enumerates `worker_nodes` | integration | `python -m pytest tests/integration/test_nodes_and_create.py -q` | ❌ W0 | ⬜ pending |
| 9-03-01 | 03 | 3 | WSX-01 | Modal defaults to Auto, sends null; manual still selectable; form valid | unit (ui) | `cd ui && npx vitest run src/components/NewWorkspaceModal.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · Wave/plan IDs are indicative; the planner finalizes.*

---

## Wave 0 Requirements

- Extend `FakeComputeProvider` with optional `node_fractions` BEFORE the selection tests can assert
  multi-node behavior (the multi-node fixture is the failing-first dependency).
- New test files: `test_fake_node_fractions.py`, `test_node_capacity_helper.py`,
  `test_node_selection.py`, `test_create_auto_node.py`, `test_nodes_and_create.py`,
  `NewWorkspaceModal.test.tsx` (names indicative; planner finalizes).

*Existing pytest + vitest infrastructure covers all phase requirements; only fixtures/tests are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Auto-select across REAL multiple Proxmox nodes with real RAM load | WSX-01 | Needs a real multi-node Proxmox cluster (deferred ACC-01) | On the homelab, configure `worker_nodes` with 2+ real nodes, create without picking, confirm the least-loaded real node is chosen. |

---

## Validation Sign-Off

- [ ] Every selection-logic task has an automated unit/integration verify
- [ ] The criterion-5 matrix is fully covered (least-loaded, over-threshold skip, boundary, tie, no-fit, manual, seam-green)
- [ ] Wave 0 (Fake `node_fractions`) precedes the selection tests
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
