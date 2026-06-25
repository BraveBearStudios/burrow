---
phase: 10
slug: persistence-data-model-reaper-carve-out
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (api); vitest + @playwright/test (ui) |
| **Config file** | `api/pyproject.toml`, `ui/playwright.config.ts`, `ui/vitest.config.ts` |
| **Quick run command** | `cd api && uv run pytest tests/unit tests/integration -q` |
| **Full suite command** | `cd api && uv run pytest -q` then `cd ui && npm run test && npm run test:e2e` |
| **Estimated runtime** | ~60–120 seconds (api); e2e adds ~1–2 min |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (scoped to the touched tier).
- **After every plan wave:** Run the full suite command.
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 120 seconds.

---

## Per-Task Verification Map

> Refined by the planner/executor with concrete task IDs. Requirement → proof anchors:

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-xx | mock-tier | 1 | TEST-01 | — | mock surfaces real UPID polling + `ResourceException` shapes | integration | `cd api && uv run pytest tests/integration/test_mock_proxmox.py -q` | ❌ W0 | ⬜ pending |
| 10-02-xx | reaper-carveout | 1 | WSX-04 | T-10-01 (data-loss bound) | reaper never destroys a persistent stopped workspace; RED if predicate regresses to state-based | unit | `cd api && uv run pytest tests/unit/test_reconciler.py -q` | ✅ | ⬜ pending |
| 10-03-xx | migration+model | 2 | WSX-02 | — | `persistent=true` survives stop→start (same id/vmid, disk intact); default ephemeral | integration | `cd api && uv run pytest tests/integration -k persistent -q` | ❌ W0 | ⬜ pending |
| 10-04-xx | e2e-hardening | 2 | TEST-02 | — | cleanup DELETE asserted `.ok()`; both Start affordances present after stop; order-independent | e2e | `cd ui && npm run test:e2e -- stop-start` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `api/tests/integration/mock_proxmox.py` — mocked-proxmoxer factory module (TEST-01 hard gate — lands first)
- [ ] `api/tests/integration/test_mock_proxmox.py` — proves the mock's UPID polling + `ResourceException` shapes
- [ ] Negative-control reaper test added to `api/tests/unit/test_reconciler.py` (WSX-04 RED-if-regressed)

*Existing infrastructure (pytest, playwright, responses, respx) otherwise covers all phase requirements — no framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Proxmox persistent stop→start with disk intact | WSX-02 | Real-infra only; CI uses Fake + mocked-proxmoxer | Deferred to Phase 14 (ACC-01) dev-homelab smoke |

*All CI-provable phase behaviors have automated verification; the real-infra acceptance is the Phase 14 gate by design.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (mock module + negative-control test)
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
