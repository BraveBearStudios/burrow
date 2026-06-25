# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reconciler — the fleet reaper + idle auto-stop (CAP-02, CAP-03).

A single ``reconcile_once()`` pass keeps the fleet healthy unattended, as the
crash safety net beyond per-step saga compensation (SC-11):

- **Reap (CAP-03):** destroy worker-pool CTs that have no live owning DB row
  (orphans / leaked VMIDs), and mark timed-out ``creating`` rows ``error`` while
  destroying their CTs. Destroy is idempotent in both providers (Pitfall 7).
- **Auto-stop (CAP-02):** stop running workspaces idle past the window, derived
  purely from the terminal connect/disconnect event log, via the GUARDED
  ``stopWorkspace(reason="idle")`` (never a raw ``stopCt``).

Every decision is a pure function of (DB state, compute state, an injected
``now``) — zero ``asyncio.sleep``, zero wall-clock except via ``self._now()`` — so
the whole reconcile is CI-provable over the Fake with no real clock or Proxmox
(FROZEN guardrail 5; ``now`` is injected, not ``freezegun``). The periodic loop
that calls this lives in the FastAPI lifespan (``main.py``); this service is the
thin-loop's pure body.

Seam discipline (CLAUDE.md, CI-enforced by ``test_seam_leakage.py``): this module
imports ONLY the two provider ABCs, ``Settings``, ``WorkspaceService``, and the
exported ``_safe`` redactor — no ``aiosqlite``, no ``proxmoxer``. The reaper drives
``compute.destroyCt`` / ``listManagedCts`` through the ABC only.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from compute.provider import ComputeProvider
from db.provider import DbProvider

from config import Settings
from lib.errors import IllegalTransitionError
from services.workspaceService import WorkspaceService, _safe

# Module logger: row-less orphan reaps log here (the events FK needs a live
# workspaceId, so a leaked VMID with no row cannot be a per-workspace event —
# FROZEN guardrail 2 / Pitfall 3). Only non-secret extras reach it.
logger = logging.getLogger("burrow.reconciler")

_TERMINAL_EVENT_TYPES = ("terminal.connected", "terminal.disconnected")


class Reconciler:
    """The fleet reaper + idle auto-stop, as one pure single-pass over the seams."""

    def __init__(
        self,
        compute: ComputeProvider,
        db: DbProvider,
        settings: Settings,
        service: WorkspaceService,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.compute = compute
        self.db = db
        self.settings = settings
        # The guarded transition for idle auto-stop goes through the service so the
        # state-machine guard, the per-workspace lock, and stoppedAt are all honored.
        self.service = service
        # Injectable clock (FROZEN guardrail 5): tests pass an explicit `now` so the
        # idle/timeout decisions are deterministic single-pass assertions — no
        # freezegun, no real wall-clock.
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(timezone.utc))

    async def reconcile_once(self) -> None:
        """Run one reconcile pass: reap first, then auto-stop idle workspaces."""
        await self._reap()
        await self._auto_stop()

    # ── reaper (CAP-03) ────────────────────────────────────────────────────
    async def _reap(self) -> None:
        """Destroy pool orphans + leaked VMIDs; sweep timed-out ``creating`` rows.

        Two cases, both pure over the current (compute, DB) snapshot:

        (A) Orphan CTs — a VMID known to compute, in the worker pool, with NO live
            DB row. Destroy it (idempotent) ON ITS REAL NODE (CR-01: ``listManagedCts``
            carries each CT's node, so an orphan off ``default_node`` is still
            destroyed, never misrouted) and log STRUCTURALLY (the events FK needs a
            live workspaceId, so a row-less reap cannot be a DB event — FROZEN
            guardrail 2). The pool-range bound is load-bearing: ``listManagedCts()``
            is unfiltered by live-ownership, so the ``vmid in pool`` + ``not live``
            re-assert MUST live here, never out-of-pool (T-04-01A / FROZEN guardrail 4).

        (B) Timed-out ``creating`` rows — stuck longer than ``creating_timeout_s``.
            These DO have a live row (so an in-flight saga's VMID is in
            ``live_vmids`` and is never an orphan, Pitfall 1). Destroy the CT,
            mark the row ``error``, and log a per-workspace ``reaper.timed_out``
            event.
        """
        pool = range(self.settings.worker_pool_start, self.settings.worker_pool_end + 1)
        managed = await self.compute.listManagedCts()
        rows = await self.db.listWorkspaces()
        live_vmids = {row.vmid for row in rows if row.vmid is not None}

        # (A) Row-less orphans in the pool → idempotent destroy + structured log.
        # CR-01: destroy each orphan against the node it ACTUALLY lives on. The
        # create saga picks an operator node per workspace (CAP-04), so an orphan
        # can sit on any node; the old hardcoded `default_node` issued the DELETE to
        # the wrong node, which the real provider 404s and swallows as idempotent
        # success — leaking the CT + VMID while logging a false `reaper.destroyed`.
        # `listManagedCts()` carries the real node, so the destroy now targets it.
        # WSX-04 carve-out (the persistence safety bound): this orphan predicate
        # keys ONLY on ownership (`vmid in live_vmids`), NEVER on `stopped` state.
        # A persistent workspace that is STOPPED keeps a live DB row (listWorkspaces
        # filters `WHERE deletedAt IS NULL`, sqliteProvider.py:192), so its vmid stays
        # in `live_vmids` and the reaper SPARES it — persistence survives stop->start
        # via this existing live-row bound, with zero state-based logic. Conversely, an
        # explicit operator delete soft-deletes the row, which drops out of
        # listWorkspaces(), so the vmid leaves `live_vmids` and the CT becomes
        # orphan-eligible: delete is NOT a persistence shield. DO NOT add a
        # `status == "stopped"` check, a `persistent` exclusion, or any state-based
        # branch here — that is the exact regression the negative-control tests
        # (test_persistent_stopped_workspace_is_never_reaped /
        # test_soft_deleted_persistent_workspace_becomes_orphan_eligible) guard against.
        for node, vmid in sorted(managed, key=lambda nv: nv[1]):
            if vmid in live_vmids or vmid not in pool:
                continue  # SAFETY BOUND: never touch a live-owned or out-of-pool CT (V4).
            await self.compute.destroyCt(node, vmid)  # idempotent, correct node
            # Row-less → no events FK to satisfy; audit via a structured log line.
            # No secret/topology in the extra (just the integer vmid).
            logger.info("reaper.destroyed", extra={"vmid": vmid})

        # (B) Timed-out `creating` rows → destroy CT + mark error + per-row event.
        deadline = self._now() - timedelta(seconds=self.settings.creating_timeout_s)
        for row in rows:
            if row.status != "creating" or row.vmid is None:
                continue
            if self._parse(row.created_at) >= deadline:
                continue  # still within the timeout — leave the in-flight create
            await self.compute.destroyCt(row.node, row.vmid)  # idempotent
            await self.db.updateWorkspace(row.id, {"status": "error"})
            # The reason is a fixed non-secret literal (NOT exception text), so it
            # is NOT routed through _safe(exc) — that takes a BaseException, not a
            # str, and is reserved for actual exception messages.
            await self.db.logEvent(row.id, "reaper.timed_out", {"reason": "creating timeout"})

    # ── idle auto-stop (CAP-02) ────────────────────────────────────────────
    async def _auto_stop(self) -> None:
        """Stop running workspaces idle past the window via the guarded transition.

        Idle = the LAST terminal event is a ``terminal.disconnected`` older than
        ``idle_window_s``. A reconnect appends a fresh ``terminal.connected``, so
        ``term[-1]`` flips back to connected → not idle (the SC-8 distinction,
        Pitfall 2). A workspace that never connected has no terminal events → not
        idle. Stops go through ``stopWorkspace(reason="idle")`` so the guard, the
        lock, and ``reason: idle`` in the event data are all honored (FROZEN
        guardrail 3).
        """
        window = timedelta(seconds=self.settings.idle_window_s)
        for row in await self.db.listWorkspaces(status="running"):
            events = await self.db.getEvents(row.id)  # oldest-first (WS-11)
            terminal_events = [e for e in events if e.type in _TERMINAL_EVENT_TYPES]
            if not terminal_events or terminal_events[-1].type != "terminal.disconnected":
                continue  # active session, or never connected → not idle
            last_disconnect = self._parse(terminal_events[-1].created_at)
            if self._now() - last_disconnect <= window:
                continue
            # WR-02: the running snapshot is taken once, but a workspace can leave
            # `running` (an operator stop, a destroy) between the snapshot and this
            # stop — `stopWorkspace` re-reads under its lock and the guard raises
            # IllegalTransitionError for the now-stopped row. Isolate each stop so
            # one raced transition does not abort the rest of THIS idle pass (which
            # would delay auto-stop fleet-wide until the next cadence tick).
            try:
                await self.service.stopWorkspace(row.id, reason="idle")
            except IllegalTransitionError:
                continue  # raced out of running between snapshot and stop — fine

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _parse(created_at: str) -> datetime:
        """Parse a stored ISO-8601 timestamp to a tz-aware UTC datetime.

        The DB writes ``...Z`` / offset-aware ISO strings; this yields an aware
        UTC datetime so the subtraction with the injected ``now`` (also aware) is
        sound. A naive timestamp is treated as UTC (the store's convention).
        """
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


# `_safe` is imported for the seam-discipline contract (the reaper routes any
# real exception text through it); it is re-exported so a future reaper path that
# logs an exception reason has the redactor available without a second import.
__all__ = ["Reconciler", "_safe"]
