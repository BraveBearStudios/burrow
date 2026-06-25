---
phase: 12
slug: setup-wizard-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio; Fake-backed integration + the Phase 10 mocked-proxmoxer tier |
| **Config file** | `api/pyproject.toml`; `api/tests/integration/conftest.py`; `api/tests/integration/mock_proxmox.py` |
| **Quick run command** | `cd api && uv run pytest tests/integration tests/unit -q` |
| **Full suite command** | `cd api && uv run pytest -q` |
| **Estimated runtime** | ~60–150 seconds |

---

## Sampling Rate

- **After every task commit:** `cd api && uv run pytest tests/integration tests/unit -q` (scoped to the touched area)
- **After every plan wave:** full `cd api && uv run pytest -q`
- **Before `/gsd:verify-work`:** full suite green + `ruff` + `mypy` clean
- **Max feedback latency:** 150 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-xx | abc+impls | 1 | SETUP-01/04 | T-12-token | testConnection/verifyTemplate on Fake+Proxmox; ephemeral client; GET-only, zero resources | unit/integration | `cd api && uv run pytest tests/integration -k "test_connection or verify_template" -q` | ❌ W0 | ⬜ pending |
| 12-02-xx | endpoints | 2 | SETUP-01/02/03 | — | `/api/v1/setup/*` envelope; readiness reuses /health; setup error codes | integration | `cd api && uv run pytest tests/integration -k setup -q` | ❌ W0 | ⬜ pending |
| 12-03-xx | token-hardening | 1 | SETUP-07 | T-12-token (HIGH-value asset) | SecretStr + logger suppression; sentinel token never in DB/envelope/log | integration | `cd api && uv run pytest tests/integration -k "sentinel or leak" -q` | ❌ W0 | ⬜ pending |
| 12-04-xx | seam+settings+adr | 2 | SETUP-04 | — | seam-leakage guard green; getSetupState read-only; ADR-0012 | unit | `cd api && uv run pytest tests/unit -k "seam or setup_state" -q` | ✅/❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] **Sentinel-token leak test** (SETUP-07 hard gate) — sentinel value absent from every DB row, the response envelope (`data`+`error`), and every emitted log line/event.
- [ ] Read-only / zero-resource assertion over the mocked-proxmoxer tier (testConnection/verifyTemplate issue only GETs; no CT/clone created).
- [ ] Missing-privilege path test (token missing privileges → success=False + exact missing names).
- [ ] Seam-leakage guard extended to the two new ABC methods (neutral DTOs; no proxmoxer type past the ABC).

*Existing infra (pytest, respx/responses, the mocked-proxmoxer tier, the Fake) covers the rest — no framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wizard validates a real Proxmox host/token + real golden template | SETUP-01/02 | Real-infra only; CI uses Fake + mocked-proxmoxer | Deferred to Phase 14 (ACC-02) dev-homelab smoke |

*All CI-provable behaviors have automated verification; the real-Proxmox wizard run is the Phase 14 gate by design.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers the sentinel-leak + read-only + missing-priv + seam tests
- [ ] No watch-mode flags
- [ ] Feedback latency < 150s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
