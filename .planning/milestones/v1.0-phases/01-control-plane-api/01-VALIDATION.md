---
phase: 1
slug: control-plane-api
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-10
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 1 — Validation Strategy

> CI proves the saga + state machine + CRUD + bootconfig over real SQLite + mocked Proxmox (`responses`) + stub ttyd. Real Proxmox clone/boot is the dev-homelab smoke gate (deferred).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio (`asyncio_mode="auto"`) |
| **Config file** | `api/pyproject.toml` (extend Phase-0 `[tool.pytest.ini_options]`) |
| **Quick run command** | `cd api && uv run pytest tests/unit -x -q` |
| **Full suite command** | `cd api && uv run pytest -q` (unit + integration) |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** `cd api && uv run pytest tests/unit -x -q` + `uv run ruff check . && uv run mypy . --strict`
- **After every plan wave:** `cd api && uv run pytest -q` (unit + integration: real SQLite + `responses` Proxmox mock + stub ttyd)
- **Before verify:** full suite + ruff + format + mypy --strict + `uv lock --check` + reuse lint green; real-Proxmox = homelab smoke (out of CI by design)
- **Max feedback latency:** ~20s

---

## Per-Req Verification Map

| Req | Behavior | Test Type | Automated Command | File | Status |
|-----|----------|-----------|-------------------|------|--------|
| WS-02 | Create saga reaches `running` over Fake | unit | `pytest tests/unit/test_create_saga.py -x` | ❌ W0 | ⬜ |
| WS-03 | Compensation: forced failure at each step → `error`, no orphan | unit | `pytest tests/unit/test_compensation.py -x` | ❌ W0 | ⬜ |
| WS-09 | Illegal transitions rejected (stop-on-creating, start-on-destroyed, double-destroy) | unit | `pytest tests/unit/test_state_machine.py -x` | ❌ W0 | ⬜ |
| CAP-01 | Create refused at node RAM > 0.80 | unit | `pytest tests/unit/test_capacity_guard.py -x` | ❌ W0 | ⬜ |
| WS-10 | Duplicate active vmid raises; destroy→recreate reuses vmid (partial unique index) | integration | `pytest tests/integration/test_vmid_reservation.py -x` | ❌ W0 | ⬜ |
| WS-01/04/05/06/07/08/11, PLAT-01 | Full `/api/v1/workspaces` CRUD + stop/start/destroy/events over real SQLite | integration | `pytest tests/integration/test_workspaces_api.py -x` | ❌ W0 | ⬜ |
| PLAT-03 | `/health` reports db + compute; degraded ≠ 500 | integration | `pytest tests/integration/test_health.py -x` | ❌ W0 | ⬜ |
| PLAT-04, PLAT-05 | Security headers on every response; CORS non-`*`; JSON logs no secrets | integration | `pytest tests/integration/test_security_headers.py -x` | ❌ W0 | ⬜ |
| WORK-03 | Bootconfig: in-pool vmid → non-secret payload; out-of-pool → 404; no cred in logs | integration | `pytest tests/integration/test_bootconfig.py -x` | ❌ W0 | ⬜ |
| WS-02 (Proxmox unit) | ProxmoxProvider UPID-block + net0 + node mem via `responses` | integration | `pytest tests/integration/test_proxmox_provider.py -x` | ❌ W0 | ⬜ |
| CICD-02/03 | Test pyramid green; failing-first regressions | static (CI) | the `ci.yml` test jobs | ❌ W0 | ⬜ |
| WS-02 (real-infra) | Real clone/start UPID + static IP + real ttyd | manual / homelab | dev-homelab five-step smoke | n/a | ⬜ deferred |

*Status: ⬜ pending · ✅ green · ❌ red. Task IDs assigned by the planner.*

---

## Wave 0 Requirements

- [ ] `tests/integration/conftest.py` — ASGITransport client + temp-SQLite + stub-ttyd fixtures
- [ ] unit: `test_create_saga.py`, `test_compensation.py`, `test_state_machine.py`, `test_capacity_guard.py`
- [ ] integration: `test_vmid_reservation.py`, `test_workspaces_api.py`, `test_health.py`, `test_security_headers.py`, `test_bootconfig.py`, `test_proxmox_provider.py`
- [ ] `pyproject.toml`: add `responses` (requests-mock for Proxmox) + `respx` (httpx ttyd-health) dev deps; extend pytest config
- [ ] Extend `migrate()` so the `002_*.sql` partial-unique-index migration actually applies (Phase-0 `migrate()` only runs `001`)

---

## Manual-Only Verifications (dev-homelab smoke — deferred)

| Behavior | Requirement | Why Manual | Test |
|----------|-------------|------------|------|
| Real `--full` clone + start, UPID blocks to OK, static net0 IP set | WS-02 | Needs real Proxmox node | Create against the node; confirm CT clones, boots, gets the VMID-derived IP |
| Real ttyd health reachable on the worker LAN | WS-02/WORK-04 | Real CT + LAN | `/health` `compute: ok`; create reaches `running` |
| Compensation tears down a real partial clone | WS-03 | Real Proxmox | Force a mid-saga failure; confirm no orphan CT, VMID freed |
| Five-step create→live→stop→start→destroy | WS-01..08 | Full real-infra path | PRIMING.md STEP 4 |

> Deferred per the operator's full-autonomous choice (no Proxmox reachable from the dev box). `human_needed`, not phase-blocking.

---

## Security Domain (ASVS L1, block_on=high)

- **bootconfig endpoint** = the one real surface: `vmid ∈ [pool_start,pool_end]` gate, 404 without echoing the probe, optional source-IP binding (defense-in-depth, not auth), **no git credential / Proxmox token in logs or event `data`**.
- CA-pinned TLS to Proxmox (`verify_ssl=<ca_path>`, never `False`).
- Parameterized SQL only; Pydantic input validation; non-`*` CORS + security headers (PLAT-05).
- v1 is **LAN-only no-auth by design** — do NOT retrofit V2/V3 auth into v1 paths. Mass-create DoS is an accepted v1 risk bounded by the capacity guard + VMID pool + LAN boundary.
- **block_on=high gates:** secrets-in-logs and `verify_ssl=False` must be absent.

---

## Validation Sign-Off

- [ ] All CI-provable reqs have an `<automated>` verify or Wave 0 dependency
- [ ] Sampling continuity maintained
- [ ] Wave 0 covers all MISSING references (incl. the `migrate()` extension)
- [ ] `responses` used for Proxmox (NOT respx — proxmoxer is requests-based)
- [ ] `nyquist_compliant: true`

**Approval:** pending
