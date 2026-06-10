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
import re

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
)

# Bounded reservation retries: each loss re-scans the (DB ∪ compute) used-set and
# tries the next free VMID. 10 is generous for a single operator on a ~100-id pool.
_RESERVE_ATTEMPTS = 10

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
            # 3 — persist non-secret boot intent (pull-at-boot DB write, ADR-0002).
            await self.compute.injectBootConfig(vmid, self._boot_config(payload))
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
            await self.db.logEvent(ws.id, "boot.error", {"reason": _safe(exc)})
            await self.db.updateWorkspace(ws.id, {"status": "error"})
            raise

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

    def _boot_config(self, payload: WorkspaceCreate) -> BootConfig:
        """Build the non-secret boot intent (no credential — pull-at-boot)."""
        return BootConfig(
            config_repo=self.settings.config_repo,
            config_branch=self.settings.config_branch,
            project_repo=payload.project_repo,
            project_branch=payload.project_branch,
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
