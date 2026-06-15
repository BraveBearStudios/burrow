<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow — Retrospective

## Milestone: v1.0 — MVP

**Shipped:** 2026-06-11
**Phases:** 5 (0-4) | **Plans:** 26

### What Was Built

A browser-accessible manager for many concurrent Claude Code sessions: contracts/seams +
hermetic Fake substrate (P0), the create→stop→start→destroy saga with a server-enforced state
machine, race-safe VMID reservation, capacity guard and the `/api/v1` envelope (P1), the
ttyd-subprotocol WebSocket terminal bridge + a tiling xterm/react-mosaic UI with reconnect and
restore-after-refresh (P2), reproducible manifest-driven workers with leak-proof boot-time
credential handling (P3), and an in-process reaper + idle auto-stop + atomic capacity lock + a
per-workspace activity drawer + the scan/SBOM/sign/SLSA→GHCR release path (P4).

### What Worked

- **Seams-first + a Fake provider** put ~80% of the backend under hermetic CI before any real
  Proxmox call existed — every phase reached a real, test-proven contract (api 173 / ui 97 / reuse
  275) with zero live infra.
- **The discuss→plan→execute→review→verify loop caught real bugs that isolated phase work missed:**
  the Phase-4 code review found a node-misrouted reaper (CR-01, would silently leak CTs on
  non-default nodes), and the **milestone integration audit found the WS-08 terminate→destroy wire
  was never connected** (the operator's "Terminate" only closed the panel). Both were fixed before
  close, each with a regression test proven to bite.
- **Pattern-mapping before planning** kept new code anchored to real in-repo analogs and surfaced
  load-bearing corrections (the `/api/v1/health` HEALTHCHECK path; the Fake's unfiltered
  `usedVmids()` forcing the reaper's pool-range bound into the reconciler).

### What Was Inefficient

- A **tooling tension** cost rework: the SPDX-comment-before-frontmatter convention (needed for
  `reuse lint`) breaks the gsd-sdk `phase-plan-index` frontmatter parser, so Phase-4 wave/dep
  grouping had to be read from raw YAML. And `uvx reuse` crashes on the Windows host without
  `--with charset-normalizer`. Phase 3 also shipped 5 planning docs without SPDX headers, tripping
  the repo-wide reuse gate at verification (fixed retroactively; Phase 4's planner pre-empted it).
- Executors initially **paused for per-commit approval** mid-run (inheriting the global gate),
  needing explicit autonomous-commit authorization in every executor/fixer prompt thereafter.

### Patterns Established

- **`human_needed` is the correct close state for an infra-bounded project:** CI proves every
  contract over the Fake; real-Proxmox/real-GHCR acceptance is the documented dev-homelab/CD smoke,
  tracked per-phase in `*-HUMAN-UAT.md` — not a CI failure.
- Every reviewer/fixer finding lands a **failing-first regression test proven to bite** (revert the
  fix → the test fails).
- ADRs for architecture deviations (ADR-0009 plugin cadence, ADR-0010 reconciler + capacity lock).

### Key Lessons

- The **milestone integration audit earns its keep** — it caught a user-facing data-flow break
  (WS-08) that five green per-phase verifications all missed, because each phase verified its own
  half and the wire between them was never made (and the e2e only asserted panel removal).
- **Make the Fake model the real provider's failure modes**, not just its happy path: the reaper
  node bug was invisible until the Fake's `destroyCt` was taught to honor `node` and 404 off-node.

### Cost Observations

- Model mix: Opus (quality profile) across orchestrator + all GSD subagents.
- Notable: the heaviest spend was the Phase-3/4 executor + code-fixer agents (full TDD + multi-file
  supply-chain work); discuss/plan/review agents were comparatively cheap.

## Milestone: v1.1 — UI Polish + Stop/Start Controls

**Shipped:** 2026-06-15
**Phases:** 2 | **Plans:** 5 | **Close state:** tech_debt (no blockers)

### What Was Built
Explicit state-machine-gated Stop/Start UI controls + a `Workspace stopped` placeholder (UI-07/08);
the three 04-UI-REVIEW drawer-polish details restored as global CSS — `--w-drawer` responsive token,
global `:focus-visible` `--accent-line` ring, custom scrollbar (UI-09/10/11); CI/tooling robustness —
`reuse` pinned to `--with charset-normalizer` and `.planning` artifacts licensed via REUSE.toml so PLAN
frontmatter stays line-1 for the parser (CICD-07/08).

### What Worked
- The discuss→ui-spec→research→pattern→plan→checker→execute→review→verify chain caught real things early:
  the planner corrected a stale research claim (test files already existed → "extend" not "create"); the
  reviewer + verifier independently confirmed the e2e and surfaced WR-01 as pre-existing, not a regression.
- Grounding the CICD work by actually running `reuse lint` first turned a vague "document a convention"
  phase into a concrete, oracle-verified fix (299/312 → 309/309).
- Failing-first Wave-0 made the feature waves pure go-green; `useTerminal` needed zero production change
  (confirmed by test), avoiding speculative rework.

### What Was Inefficient
- The executor honored the global per-commit approval gate and paused mid-plan (05-04) — the orchestrator
  had to finalize the commit/SUMMARY inline. Worth aligning the subagent commit posture with the run's
  "gate at phase boundaries" decision up front.
- Bash cwd drifted into `ui/` after a `cd ui` gate, causing a confusing `cd api` failure — absolute paths
  in orchestrator shell calls would avoid it.
- Phase 6 was small enough that the full planner/checker/executor fleet was overkill; executed inline.

### Patterns Established
- **jsdom boundary discipline:** V2 width / V3 `:focus-visible` / V4 scrollbar are CSS-source asserts (vitest)
  or Playwright live assertions — never computed-style/pseudo-class in jsdom. Encoded in VALIDATION.md.
- **Planning-artifact licensing (CICD-08):** `.planning/**` md/json licensed via REUSE.toml, PLAN frontmatter
  line-1; source files keep inline headers (CICD-06 preserved).

### Key Lessons
- Surface pre-existing debt found during in-scope review as backlog todos, don't silently expand phase scope.
- An infra phase's "test" can be a tool oracle (`reuse lint` + parser), not a code test pyramid.

### Cost Observations
- Model mix: Opus across orchestrator + all GSD subagents. Heaviest spend: the four Phase-5 executors
  (real React/CSS + tests + a live Playwright run). Phase 6 executed inline (cheap).

## Cross-Milestone Trends

| Milestone | Phases | Plans | Close state | Blockers found at audit |
|-----------|--------|-------|-------------|--------------------------|
| v1.0 MVP | 5 | 26 | tech_debt (real-infra deferred) | 1 (WS-08 terminate→destroy; fixed) |
| v1.1 UI Polish + Stop/Start | 2 | 5 | tech_debt (no blockers; WR-01/02 → backlog) | 0 |
