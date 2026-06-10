# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""WorkspaceService — the lifecycle orchestration core (WS-01..09, CAP-01/04).

The single policy authority for the create/stop/start/destroy lifecycle. It runs
the SC-corrected create saga (RESEARCH Pattern 2): persist a ``creating`` row with
a DB-reserved VMID BEFORE cloning, await each provider mutation (the provider
blocks on the Proxmox UPID internally, SC-1), and on ANY post-reservation failure
run idempotent reverse compensation that frees the VMID and lands the row in
``error`` — never stuck ``creating`` (SC-11, Pitfall 4).

Seam discipline (CLAUDE.md): this service depends ONLY on the two provider ABCs
(:class:`ComputeProvider`, :class:`DbProvider`) and ``Settings``. It imports no
``aiosqlite`` and no ``proxmoxer`` — the seam-leakage guard enforces this. The
capacity *threshold* and the state-transition *table* are service-owned policy,
not provider concerns.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx

from compute.provider import ComputeProvider
from db.provider import DbProvider, VmidTakenError
from models.compute import BootConfig
from models.workspace import Workspace, WorkspaceCreate

from config import Settings
from lib.errors import (
    CapacityError,
    NoFreeVmidError,
    WorkspaceBootError,
    WorkspaceNotFoundError,
)
from lib.statemachine import assert_transition

# Bounded reservation retries: each loss re-scans the (DB ∪ compute) used-set and
# tries the next free VMID. 10 is generous for a single operator on a ~100-id pool.
_RESERVE_ATTEMPTS = 10

# Module logger: only whitelisted, non-secret extras reach it (lib.logging drops
# anything outside its allow-list), so a credential value can never leak here.
logger = logging.getLogger("burrow.workspace")

_REDACTED = "[redacted]"

# URL userinfo creds (``https://user:token@host``) -> keep scheme/host, mask creds.
_URL_USERINFO = re.compile(r"://[^/\s:@]+:[^/\s@]+@")

# Secret-shaped substrings to scrub from any text that reaches an event/log
# (T-01-09 / ASVS V7). Covers common git/CI token prefixes, key=value secrets, and
# a long-opaque-token entropy backstop.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"gh[posru]_[A-Za-z0-9]{6,}"),  # GitHub PAT / fine-grained / OAuth
    re.compile(r"glpat-[A-Za-z0-9_-]{6,}"),  # GitLab PAT
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{6,}"),  # Slack
    re.compile(r"(?i)\b(?:token|password|secret|api[_-]?key)\b\s*[=:]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),  # long opaque token (entropy backstop)
)


def _safe(exc: BaseException) -> str:
    """Return a redacted, bounded reason string for an exception (no secrets).

    Replaces secret-shaped substrings with ``[redacted]`` and caps the length so a
    credential, a repo-embedded token, or an over-long internal dump never reaches
    a ``boot.error`` event or a log line. The exception *type* is preserved (it is
    non-secret and useful for triage); the *message* is scrubbed.
    """
    message = _URL_USERINFO.sub("://" + _REDACTED + "@", str(exc))
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub(_REDACTED, message)
    message = message[:200]
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


class WorkspaceService:
    """Create/stop/start/destroy orchestration over the provider ABCs."""

    def __init__(
        self,
        compute: ComputeProvider,
        db: DbProvider,
        settings: Settings,
    ) -> None:
        self.compute = compute
        self.db = db
        self.settings = settings
        # Per-workspace in-flight lock: serializes concurrent mutations on a single
        # workspace id within this process (SC-12, A2). Created lazily per id and
        # RECLAIMED when the workspace is destroyed (WR-02) so the dict does not grow
        # unbounded over the process lifetime. The DB status-guarded read-then-act
        # inside the lock is the cross-process backstop (the reservation index covers
        # create-create).
        self._locks: dict[str, asyncio.Lock] = {}

    # ── create saga (WS-01/02/03, CAP-01/04) ──────────────────────────────
    async def createWorkspace(self, payload: WorkspaceCreate) -> Workspace:
        """Run the 8-step create saga; compensate to ``error`` on any failure.

        Steps (RESEARCH Pattern 2): (0) capacity guard; (1) reserve VMID + persist
        ``creating`` row; (2) clone (UPID-blocked); (3) inject boot config (DB
        write); (4) start (UPID-blocked); (5) resolve static IP; (6) await ttyd
        health; (7) mark ``running``. Any failure after step 1 triggers idempotent
        stop+destroy, a redacted ``boot.error`` event, and ``status=error``.
        """
        # 0 — capacity guard (CAP-01); node is operator-selected (CAP-04).
        if await self.compute.getNodeMemory(payload.node) > self.settings.capacity_threshold:
            raise CapacityError(payload.node)

        # 1 — reserve VMID via the DB partial-unique INSERT (the race arbiter).
        ws = await self._reserve_vmid_and_row(payload)
        vmid = ws.vmid
        assert vmid is not None  # reservation always assigns a vmid

        try:
            # 2 — clone the golden template (provider blocks on the UPID, SC-1).
            await self.compute.cloneCt(
                self.settings.template_vmid, vmid, payload.name, payload.node
            )
            # 3 — persist boot intent (pull-at-boot DB checkpoint, ADR-0002). WR-03:
            # the per-workspace boot intent (project repo/branch) is the row data
            # persisted at step 1; the global config repo/branch is derived from
            # settings at read time by the bootconfig endpoint. There is no provider
            # push (no pct/cloud-init), so this step is a DELIBERATE DB-state
            # checkpoint, not a provider call: it records that the intent is
            # captured and recoverable (SC-2), and fails loudly if the row's
            # persisted intent does not match what the bootconfig endpoint will
            # serve — rather than the old dead `injectBootConfig` no-op that claimed
            # to persist intent but wrote nothing.
            await self._persist_boot_intent(ws, payload)
            # 4 — start the container (UPID-blocked).
            await self.compute.startCt(payload.node, vmid)
            # 5 — resolve the static IP from the VMID (computed, not polled).
            ip = await self.compute.getIp(payload.node, vmid)
            await self.db.updateWorkspace(ws.id, {"lxc_ip": ip})
            # 6 — await ttyd health (httpx poll; injectable for the unit tier).
            await self._wait_ttyd(ip)
            # 7 — mark running.
            await self.db.logEvent(ws.id, "workspace.created", {})
            return await self.db.updateWorkspace(ws.id, {"status": "running"})
        except Exception as exc:
            await self._compensate(payload.node, vmid)
            # Land the row in `error` FIRST and guard it — this is the SC-11
            # guarantee (never stuck `creating`, Pitfall 4). A failure in the
            # status write or the best-effort event log must NOT mask the
            # original boot exception, so each lands in its own try/except and we
            # re-raise `exc` explicitly (a bare `raise` could rebind to a guarded
            # call's exception if one ever escaped).
            try:
                await self.db.updateWorkspace(ws.id, {"status": "error"})
            except Exception:
                pass  # never mask the original boot failure
            try:
                await self.db.logEvent(ws.id, "boot.error", {"reason": _safe(exc)})
            except Exception:
                pass  # event log is best-effort diagnostics, not the landing
            raise exc

    async def _reserve_vmid_and_row(self, payload: WorkspaceCreate) -> Workspace:
        """Reserve a VMID by INSERT under the partial-unique index (SC-3/SC-4).

        ``getNextVmid`` is a pure scan over the (compute ∪ DB) used-set; the
        atomic reservation is the ``createWorkspace`` INSERT. A ``VmidTakenError``
        means another saga won the race for that VMID — re-scan and retry, bounded
        by :data:`_RESERVE_ATTEMPTS`. Pool exhaustion raises ``NoFreeVmidError``.
        """
        base = {
            "name": payload.name,
            "node": payload.node,
            "project_repo": payload.project_repo,
            "project_branch": payload.project_branch,
            "plugin_set": payload.plugin_set,
            "status": "creating",
        }
        for _ in range(_RESERVE_ATTEMPTS):
            used = await self.compute.usedVmids() | await self._db_used_vmids()
            vmid = await self.compute.getNextVmid(
                self.settings.worker_pool_start, self.settings.worker_pool_end, used
            )
            try:
                return await self.db.createWorkspace({**base, "vmid": vmid})
            except VmidTakenError:
                continue  # lost the race; re-scan and retry
        raise NoFreeVmidError(
            "no free VMID could be reserved after "
            f"{_RESERVE_ATTEMPTS} attempts in "
            f"[{self.settings.worker_pool_start}, {self.settings.worker_pool_end}]"
        )

    async def _db_used_vmids(self) -> set[int]:
        """VMIDs the DB currently considers live (active, non-soft-deleted rows)."""
        rows = await self.db.listWorkspaces()
        return {row.vmid for row in rows if row.vmid is not None}

    async def _compensate(self, node: str, vmid: int) -> None:
        """Idempotent reverse teardown: stop then destroy, tolerating absence.

        Frees the reserved VMID by destroying the (possibly not-yet-cloned)
        container. ``destroyCt`` is a no-op on a missing CT (Pitfall 7), so a
        failure at step 2 and a failure at step 6 both clean up safely. Errors
        during compensation are swallowed so the original failure (and the
        row->error landing) is never masked.
        """
        try:
            await self.compute.stopCt(node, vmid)
        except Exception:
            pass  # best-effort: a not-running CT cannot be stopped
        try:
            await self.compute.destroyCt(node, vmid)
        except Exception:
            pass  # best-effort: destroy of a missing CT is a no-op

    # ── stop / start / destroy (WS-06/07/08/09) ───────────────────────────
    async def stopWorkspace(self, workspace_id: str) -> Workspace:
        """Stop a running workspace; state preserved (WS-06).

        Guarded by ``assert_transition(running, stop)``; the provider blocks on the
        UPID. Sets ``stoppedAt`` and logs ``workspace.stopped``.
        """
        async with self._lock_for(workspace_id):
            ws = await self._get_or_raise(workspace_id)
            assert_transition(ws.status, "stop")  # WS-09 guard (running only)
            assert ws.vmid is not None
            await self.compute.stopCt(ws.node, ws.vmid)
            updated = await self.db.updateWorkspace(
                ws.id, {"status": "stopped", "stopped_at": self._now()}
            )
            await self.db.logEvent(ws.id, "workspace.stopped", {})
            return updated

    async def startWorkspace(self, workspace_id: str) -> Workspace:
        """Start a stopped workspace and await ttyd health (WS-07).

        Guarded by ``assert_transition(stopped, start)``; re-resolves the IP and
        awaits ttyd before marking ``running``. Logs ``workspace.started``.
        """
        async with self._lock_for(workspace_id):
            ws = await self._get_or_raise(workspace_id)
            assert_transition(ws.status, "start")  # WS-09 guard (stopped only)
            assert ws.vmid is not None
            await self.compute.startCt(ws.node, ws.vmid)
            ip = await self.compute.getIp(ws.node, ws.vmid)
            await self.db.updateWorkspace(ws.id, {"lxc_ip": ip})
            await self._wait_ttyd(ip)  # WS-07: await ttyd health
            updated = await self.db.updateWorkspace(ws.id, {"status": "running"})
            await self.db.logEvent(ws.id, "workspace.started", {})
            return updated

    async def destroyWorkspace(self, workspace_id: str) -> None:
        """Stop (if running) then destroy the CT and soft-delete the row (WS-08).

        Guarded by ``assert_transition(<state>, destroy)`` (legal from running /
        stopped / error). ``destroyCt`` is idempotent (no-op on a missing CT). Sets
        ``destroyedAt``, logs ``workspace.destroyed``, then soft-deletes the row.
        """
        async with self._lock_for(workspace_id):
            ws = await self._get_or_raise(workspace_id)
            assert_transition(ws.status, "destroy")  # WS-09 guard
            assert ws.vmid is not None
            if ws.status == "running":
                await self.compute.stopCt(ws.node, ws.vmid)
            await self.compute.destroyCt(ws.node, ws.vmid)  # idempotent
            await self.db.updateWorkspace(
                ws.id, {"status": "destroyed", "destroyed_at": self._now()}
            )
            await self.db.logEvent(ws.id, "workspace.destroyed", {})
            await self.db.softDeleteWorkspace(ws.id)
        # WR-02: the workspace is terminal (soft-deleted) — no future caller will
        # ever need its lock, so reclaim the dict entry to bound _locks growth.
        # Popped AFTER releasing the lock (outside the `async with`) so we never
        # mutate the registry while the lock is held; the local `async with`
        # reference kept the object alive for the duration of this call.
        self._locks.pop(workspace_id, None)

    # ── bootconfig (WORK-03 / ADR-0002) ───────────────────────────────────
    async def get_by_vmid(self, vmid: int) -> Workspace:
        """Return the active workspace owning ``vmid`` or raise (bootconfig lookup).

        Delegates to the DB seam's ``getByVmid`` (active, non-soft-deleted rows
        only). Raises :class:`WorkspaceNotFoundError` when no live workspace owns
        ``vmid`` so the bootconfig router can map both the no-workspace and the
        destroyed-vmid cases to the same 404 (WORK-03; pull-at-boot, ADR-0002).
        """
        ws = await self.db.getByVmid(vmid)
        if ws is None:
            # Keyed by the vmid for triage; the router emits a generic 404 (no echo).
            raise WorkspaceNotFoundError(str(vmid))
        return ws

    async def mint_repo_credential(self, repo: str) -> str:
        """Return a git credential for a boot fetch — a DEV PLACEHOLDER, not a real cred.

        PLUGGABLE issuance seam (RESEARCH Open Question 1 / Assumption A3), pending the
        operator's A3 decision. **v1 does NOT mint a real short-lived, per-repo-scoped
        credential.** It returns either (a) a clearly-marked dev placeholder string when
        ``settings.git_credential_token`` is unset, or (b) the configured
        ``git_credential_token`` value verbatim — a single, static, process-wide value
        that is NOT scoped to ``repo`` and does NOT expire. ``repo`` is recorded only as
        the scope the *real* issuer will eventually bind to; the current body ignores it
        for issuance.

        Because the configured-token path serves one global value to every repo and
        caller, this method emits a structured warning whenever it serves a non-empty
        ``git_credential_token`` so the "not actually repo-scoped" reality is visible in
        the logs — it is the operator's signal that this is a stopgap, not the A3 issuer.

        Operator action (A3, MUST be resolved before Phase 3 wires ``burrow-boot.sh``):
        replace this body with a real minting mechanism — a GitHub App installation
        token, a repo deploy token, or an ephemeral fine-grained PAT — that is
        short-lived and single-repo-scoped, NEVER a long-lived PAT, and NEVER logged or
        persisted to the worker env (ADR-0002). The worker uses the credential once for
        ``git clone`` and discards it. Do NOT hard-code a long-lived PAT here, and treat
        a non-empty ``git_credential_token`` in multi-repo use as a misconfiguration
        until the real issuer lands.
        """
        token = self.settings.git_credential_token
        if token:
            # NOT repo-scoped and NOT short-lived: surface the stopgap loudly so an
            # operator never mistakes the global token for the real A3 issuer. The
            # token value itself is NEVER logged (only the repo it is served for).
            logger.warning(
                "serving the global, non-repo-scoped git_credential_token (A3 dev "
                "stopgap, NOT a per-repo short-lived credential)",
                extra={"repo": repo},
            )
            return token
        # No token configured: an explicitly non-production placeholder, never a
        # real credential. The DEV-PLACEHOLDER marker makes a leak obvious in triage.
        return f"DEV-PLACEHOLDER-NOT-A-REAL-CREDENTIAL:{repo}"

    # ── lifecycle helpers ──────────────────────────────────────────────────
    def _lock_for(self, workspace_id: str) -> asyncio.Lock:
        """Return the per-workspace in-flight lock, creating it on first use."""
        lock = self._locks.get(workspace_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[workspace_id] = lock
        return lock

    async def _get_or_raise(self, workspace_id: str) -> Workspace:
        """Load an active workspace or raise ``WorkspaceNotFoundError``."""
        ws = await self.db.getWorkspace(workspace_id)
        if ws is None:
            raise WorkspaceNotFoundError(workspace_id)
        return ws

    @staticmethod
    def _now() -> str:
        """ISO-8601 UTC timestamp for the lifecycle ``*_at`` columns."""
        return datetime.now(timezone.utc).isoformat()

    def _boot_config(self, payload: WorkspaceCreate) -> BootConfig:
        """Build the non-secret boot intent (no credential — pull-at-boot)."""
        return BootConfig(
            config_repo=self.settings.config_repo,
            config_branch=self.settings.config_branch,
            project_repo=payload.project_repo,
            project_branch=payload.project_branch,
        )

    async def _persist_boot_intent(self, ws: Workspace, payload: WorkspaceCreate) -> None:
        """Saga step 3: record that the boot intent is captured + recoverable (WR-03).

        Pull-at-boot (ADR-0002) means the worker fetches its boot config from the
        control plane at boot, derived from (a) the per-workspace project repo/branch
        persisted on the reservation row at step 1 and (b) the global config
        repo/branch from settings. Nothing is pushed into the CT, so this step is a
        DELIBERATE DB-state checkpoint rather than a provider call.

        It does real, verifiable work: it asserts the persisted row's project
        repo/branch match the create payload (the intent the bootconfig endpoint will
        serve), failing loudly with a ``WorkspaceBootError`` if they ever diverge —
        and logs a ``bootconfig.persisted`` event so the captured intent is auditable
        for recovery. This replaces the old ``injectBootConfig`` no-op that claimed to
        persist intent but mutated nothing.
        """
        config = self._boot_config(payload)
        if (ws.project_repo, ws.project_branch) != (config.project_repo, config.project_branch):
            raise WorkspaceBootError(
                "persisted boot intent does not match the create payload "
                f"for workspace {ws.id}"
            )
        await self.db.logEvent(
            ws.id,
            "bootconfig.persisted",
            {
                "config_repo": config.config_repo,
                "config_branch": config.config_branch,
                "project_repo": config.project_repo,
                "project_branch": config.project_branch,
            },
        )

    async def _wait_ttyd(self, ip: str | None) -> None:
        """Poll the worker's ttyd health endpoint until ready or timeout (step 6).

        Injectable: the unit tier monkeypatches this to resolve instantly (no
        network); the integration tier exercises the real poll against a stub ttyd.
        A non-5xx response means ttyd is serving; connect/timeout errors are
        retried until ``ttyd_timeout`` elapses, then it raises.
        """
        if ip is None:
            raise WorkspaceBootError("no IP resolved for the worker; cannot reach ttyd")
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.settings.ttyd_timeout
        async with httpx.AsyncClient() as client:
            while loop.time() < deadline:
                try:
                    response = await client.get(f"http://{ip}:7681/", timeout=2)
                    if response.status_code < 500:
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                await asyncio.sleep(self.settings.ttyd_interval)
        raise WorkspaceBootError(f"ttyd not ready in {self.settings.ttyd_timeout}s")


__all__ = ["WorkspaceService", "_safe"]
