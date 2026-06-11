<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0010: In-process fleet reconciler and a process-level capacity lock

## Status

Accepted

## Context

Phase 4 (Hardening & Release) adds two pieces of unattended-fleet machinery that
both hinge on a shared assumption about how the control plane runs, so they are
recorded together:

1. **A fleet reconciler** (CAP-02/CAP-03) that, on a periodic cadence, reaps
   orphaned Proxmox CTs and leaked VMIDs, times out stuck `creating` rows to
   `error`, and auto-stops idle workspaces. Without it the fleet drifts: a crashed
   create leaks a VMID, a hard-deleted row strands a running CT, an abandoned
   terminal holds a node's RAM indefinitely.
2. **A capacity-under-concurrency fix** (CAP-02). The create saga's step-0 node-RAM
   guard and its step-1 VMID reservation are two separate, unserialized steps
   (`workspaceService.py`: capacity read, then `_reserve_vmid_and_row`). The
   shipped partial-unique INSERT (002) already stops two creates from taking the
   *same* VMID, but it does NOT stop two concurrent creates from both passing a
   *stale* capacity read and overcommitting a node (Pitfall 5): both read node RAM
   under threshold, both reserve different VMIDs, both clone.

Both decisions turn on the same load-bearing fact about the v1 self-host
deployment: **the API runs as a single process (`--workers 1`).** v1 is LAN-only,
single-operator, no auth (CLAUDE.md security posture), and the SQLite store is the
single-host path (ADR-0001). Under that topology an in-process construct is
sufficient and is the simplest thing that works; a multi-process deployment would
need a different backstop, and that upgrade path must be recorded, not assumed
away.

For the reconciler runtime, two shapes were considered:

- **A. External scheduler** — a systemd timer or cron entry invokes a reconcile
  command. Adds a second deployment artifact and a second failure surface (the
  timer can drift, double-fire, or silently stop) for a single self-host process,
  and splits the lifecycle from the app that owns the provider seams.
- **B. In-process asyncio periodic task (chosen)** — one background task, owned by
  the FastAPI `lifespan`, runs both reaping and idle auto-stop on a fixed period.
  No external artifact, shares the already-wired `ComputeProvider`/`DbProvider`
  seams, and starts/stops deterministically with the app.

For the capacity race, CONTEXT explicitly allows either a lock or a transaction:

- **C. Process-level `asyncio.Lock` (chosen for v1)** — serialize the capacity
  read with the reservation in one critical section within the single process.
- **D. `BEGIN IMMEDIATE` transaction** — re-read capacity inside a write
  transaction so serialization holds across processes. Necessary only under
  `--workers >1`; heavier than needed for a single process.

## Decision

Adopt **Option B** for the reconciler and **Option C** for the capacity race, as
two facets of the single-process v1 assumption.

- **One in-process reconciler, two responsibilities.** The fleet reconciler is a
  SINGLE asyncio periodic task started and cancelled by the FastAPI `lifespan` —
  no external cron or systemd timer. One loop performs BOTH reaping (orphan CTs,
  leaked VMIDs, timed-out `creating` rows) and idle auto-stop. Its cadence is
  configured by non-secret `Settings` keys: `reconciler_period_s` (loop period),
  `creating_timeout_s` (when a `creating` row is reaped to `error`), and
  `idle_window_s` (how long a running workspace may be idle before auto-stop). The
  loop body wraps each pass in a broad `except` so one failed pass cannot kill the
  task, and `lifespan` cancels it then suppresses `CancelledError` on shutdown.

- **A process-level `asyncio.Lock` closes the capacity race.** A single
  process-wide `self._create_lock` in `WorkspaceService` wraps EXACTLY the step-0
  capacity guard and the step-1 VMID reservation, so two concurrent creates cannot
  both pass a stale node-RAM read. The lock is **released before the multi-second
  clone**, so concurrent creates still parallelize their slow saga steps — it
  serializes only the check+reserve, not the whole saga. The VMID partial-unique
  INSERT (ADR-0001 / migration 002) remains the cross-process race arbiter for
  VMID *uniqueness* and is unchanged; this lock only closes the *capacity-read*
  gap.

- **The `--workers >1` upgrade path is `BEGIN IMMEDIATE`, deferred.** If a future
  self-host topology ever runs more than one API process, the in-process lock no
  longer serializes across processes. The documented replacement is to wrap the
  capacity re-read and the reservation in a SQLite `BEGIN IMMEDIATE` write
  transaction (Option D), which acquires the database write lock before the read
  so the serialization holds cross-process. This is deferred (RESEARCH A1 / Open
  Q3): v1 ships `--workers 1`, so the lock is sufficient and is the KISS choice.

## Consequences

- One background task carries two responsibilities (reap + auto-stop). This keeps
  the runtime minimal for the single self-host process, at the cost that the two
  concerns share a cadence and a failure-isolation boundary; if they ever need
  independent periods or isolation they split into two tasks.
- The capacity lock is **per-process**. Under the v1 `--workers 1` assumption it
  fully closes Pitfall 5; under a hypothetical `--workers >1` deploy it would NOT,
  and the `BEGIN IMMEDIATE` transaction backstop above MUST be adopted first.
- The VMID partial-unique INSERT remains the cross-process arbiter for VMID
  uniqueness **regardless** of the capacity lock or worker count — it is the
  durable guarantee, the lock is the capacity-read serializer layered on top.
- No external scheduler artifact is introduced, so there is no second lifecycle to
  deploy, monitor, or keep in sync; the reconciler lives and dies with the app.
- Idle auto-stop is **STOP, not destroy** (CONTEXT): the workspace is preserved and
  restartable, emitting `workspace.stopped` with `reason: idle`, consistent with
  the SC-8 detach-not-terminate semantics — a brief disconnect/reconnect must not
  trip it.

## Revisit trigger

A confirmed `--workers >1` self-host topology (which invalidates the per-process
lock and forces the `BEGIN IMMEDIATE` transaction backstop), or a move to an
external scheduler for the reconciler (e.g. if reaping must run independently of
the API process lifecycle, or the two responsibilities need separate cadences /
failure isolation).
