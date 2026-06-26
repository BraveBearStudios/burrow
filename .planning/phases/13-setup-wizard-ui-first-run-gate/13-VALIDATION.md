---
phase: 13
slug: setup-wizard-ui-first-run-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (jsdom + MSW) for components/hooks; @playwright/test (Fake-backed 3-process webServer) for e2e; pytest for the 2 new backend endpoints |
| **Config file** | `ui/vitest.config.ts`, `ui/playwright.config.ts`, `api/pyproject.toml` |
| **Quick run command** | `cd ui && npm run test` (vitest) |
| **Full suite command** | `cd ui && npm run test && npm run test:e2e` then `cd api && uv run pytest tests/integration -k setup -q` |
| **Estimated runtime** | ~30–60s vitest; +1–2 min e2e |

---

## Sampling Rate

- **After every task commit:** scoped `cd ui && npm run test` (or the api setup pytest for backend tasks)
- **After every plan wave:** full vitest + the setup e2e + api setup tests
- **Before `/gsd:verify-work`:** full suite green; biome + tsc clean
- **Max feedback latency:** 120 seconds (e2e excluded from the per-commit loop)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-xx | backend-setter | 1 | SETUP-04 | — | setSetupCompleted + GET /setup/state + POST /setup/complete (idempotent) | integration (pytest) | `cd api && uv run pytest tests/integration -k setup -q` | ❌ W0 | ⬜ pending |
| 13-02-xx | hooks+checkbox | 1 | WSX-02 | — | useSetupState/useCompleteSetup hooks; persistent checkbox → body.persistent | unit (vitest) | `cd ui && npm run test -- NewWorkspaceModal` | ❌ W0 | ⬜ pending |
| 13-03-xx | wizard+gate | 2 | SETUP-04/05/06 | — | SetupWizard gate; 4 auto-advance steps; re-probe→first-failing; complete-after-create | unit (vitest) | `cd ui && npm run test -- SetupWizard` | ❌ W0 | ⬜ pending |
| 13-04-xx | e2e | 2 | SETUP-04/05/06 | — | unconfigured shows gate→walk→complete→gate vanishes; configured skips gate | e2e (playwright) | `cd ui && npm run test:e2e -- setup-wizard` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Backend setup integration tests (state null → complete → state set; idempotent setter).
- [ ] `SetupWizard.test.tsx` (gate shows on null; auto-advance; failing-step error+retry; re-probe jump; complete-after-create).
- [ ] `NewWorkspaceModal.test.tsx` persistent-checkbox case (checked → body.persistent=true; default false).
- [ ] `tests/e2e/setup-wizard.spec.ts` (gate flow over the Fake).

*Existing infra (vitest+MSW, Playwright 3-process harness, pytest Fake-backed app) covers the rest — no framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real first-workspace-on-real-Proxmox via the wizard | SETUP-04 | Real-infra only; CI uses Fake | Deferred to Phase 14 (ACC-01) dev-homelab smoke |

*All CI-provable behaviors have automated verification; the real wizard walkthrough is the Phase 14 gate by design.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers backend setter + wizard + checkbox + e2e
- [ ] No watch-mode flags (vitest run, not watch)
- [ ] Feedback latency < 120s (e2e excluded from per-commit loop)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
