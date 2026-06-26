# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proxmox compute provider — real ``proxmoxer`` implementation (PLAT-07).

This is the only file permitted to import ``proxmoxer``/``ProxmoxAPI`` (seam-leakage
discipline, PLAT-06/07): every Proxmox symbol stays confined here, and only the typed
:class:`compute.provider.ComputeError` subclasses cross the ABC back to the saga.

Three landmines are handled here (RESEARCH Pitfalls 1, 2, 5):

1. ``proxmoxer`` is *synchronous* (requests-based). The ABC methods are ``async``, so
   EVERY blocking proxmoxer call runs in :func:`asyncio.to_thread` — an un-wrapped call
   would stall the whole event loop for the duration of a multi-second clone.
2. Each mutating call (clone/start/stop/destroy) returns a Proxmox UPID *immediately*;
   the work runs async on the node. We block on that UPID via
   ``proxmoxer.tools.Tasks.blocking_status`` and assert ``exitstatus == "OK"`` BEFORE
   returning, so the saga can never race clone→start (SC-1).
3. TLS is CA-pinned: ``verify_ssl=settings.proxmox_ca_cert_path`` (a CA-cert path
   forwarded to ``requests`` ``verify``). Disabling verification is forbidden
   (CLAUDE.md security posture; block_on=high gate).

The static worker IP is computed from the VMID (ADR-0004) — no DHCP poll, no guest agent
(unprivileged LXC have none). The same formula drives both the ``net0`` set at clone time
and :meth:`getIp`, so the control plane's address and the worker's address can never drift.
On clone the new VMID is added to ``/pool/burrow-workers`` (ADR-0003) so the pool-scoped
token retains rights over the clone it just created.
"""

import asyncio
import ipaddress
from typing import Any

import proxmoxer
from proxmoxer.tools import Tasks

from models.compute import (
    BootConfig,
    ComputeStatus,
    ComputeTask,
    ConnectionResult,
    TemplateResult,
)

from compute.provider import (
    CloneError,
    ComputeProvider,
    LxcNotReadyError,
    NoFreeVmidError,
    SetupAuthError,
    SetupUnreachableError,
    TaskFailedError,
)

# The resource pool every worker clone is added to so the pool-scoped token keeps
# rights over its own clone (ADR-0003).
_WORKER_POOL = "burrow-workers"

# The documented BurrowProvisioner privilege set host-prime's `00-api-user-role.sh`
# grants (SETUP-01). testConnection asserts these are present in the privsep token's
# EFFECTIVE permissions and reports any missing — it creates none.
REQUIRED_PRIVS: frozenset[str] = frozenset(
    {
        "VM.Audit",
        "VM.Clone",
        "VM.Allocate",
        "VM.Config.Network",
        "VM.Config.Options",
        "VM.PowerMgmt",
        "Datastore.AllocateSpace",
        "Datastore.Audit",
        "Sys.Audit",
    }
)


class ProxmoxComputeProvider(ComputeProvider):
    """Proxmox-backed :class:`ComputeProvider` over a synchronous ``proxmoxer`` client."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        # CA-pinned TLS: pass the CA-cert path to requests' `verify`; never disable
        # verification (CLAUDE.md security posture; block_on=high gate).
        self._api = proxmoxer.ProxmoxAPI(
            settings.proxmox_host,
            user=settings.proxmox_user,
            token_name=settings.proxmox_token_name,
            # SETUP-07: `proxmox_token_value` is a SecretStr; the real value is read
            # ONLY here, at the proxmoxer boundary, via .get_secret_value().
            token_value=settings.proxmox_token_value.get_secret_value(),
            verify_ssl=settings.proxmox_ca_cert_path,
        )

    # ── internal helpers ──────────────────────────────────────────────────────
    async def _block(self, upid: str, timeout: float) -> ComputeTask:
        """Block on a UPID task to completion; assert ``exitstatus == "OK"`` (SC-1).

        ``Tasks.blocking_status`` polls the node until the task leaves ``running`` or the
        timeout elapses, returning a status dict (``None`` on timeout). Runs in a worker
        thread so the synchronous poll never stalls the event loop (Pitfall 2).

        WR-06: the three failure modes are reported with DISTINCT messages so an
        operator can tell them apart in real-infra triage — a timeout, a task still
        running / in an unknown state, and a stopped-but-non-OK exit are no longer
        conflated. Every message carries the UPID; the non-OK message also carries
        the actual ``exitstatus``.
        """
        status = await asyncio.to_thread(Tasks.blocking_status, self._api, upid, timeout)
        # Mode 1 — timeout: blocking_status returned None (deadline hit while running).
        if status is None:
            raise TaskFailedError(f"task {upid} timed out after {timeout}s (still running)")
        # Mode 2 — still running / unknown: a status dict that is present but not
        # 'stopped' (some proxmoxer versions return the last-seen running snapshot
        # rather than None). Distinct from a stopped-but-failed task.
        task_state = status.get("status")
        if task_state != "stopped":
            raise TaskFailedError(
                f"task {upid} did not stop (status={task_state!r}) within {timeout}s"
            )
        # Mode 3 — stopped but non-OK: the task finished with a failure exitstatus.
        exitstatus = status.get("exitstatus")
        if exitstatus != "OK":
            raise TaskFailedError(f"task {upid} stopped with exitstatus={exitstatus!r}")
        return ComputeTask(upid=upid, status="ok", exitstatus=exitstatus)

    def _ip_for(self, vmid: int) -> str:
        """Compute the worker's static IP from its VMID (ADR-0004).

        The VMID's last octet maps into the worker subnet's host range. A VMID outside
        the subnet's host space is a configuration error, surfaced here rather than
        producing a silently-wrong address.
        """
        network = ipaddress.ip_network(self._settings.worker_subnet, strict=False)
        host = vmid % 256
        address = network.network_address + host
        if address not in network:
            raise CloneError(f"VMID {vmid} maps to {address}, outside worker subnet {network}")
        return str(address)

    def _net0_for(self, vmid: int) -> str:
        """Build the ``net0`` config string for ``vmid`` (ADR-0004).

        ``ip=`` takes CIDR (host/prefix); ``gw=`` a bare gateway IP. All topology values
        come from ``Settings`` (placeholders in-repo; the real LAN lives in gitignored
        ``.env``).
        """
        s = self._settings
        return (
            f"name=eth0,bridge={s.worker_bridge},"
            f"ip={self._ip_for(vmid)}/{s.worker_prefix},gw={s.worker_gateway}"
        )

    # ── VMID allocation ───────────────────────────────────────────────────────
    async def getNextVmid(self, pool_start: int, pool_end: int, used: set[int]) -> int:
        # Pure scan over the caller's snapshot — NOT a reservation (the DB partial-unique
        # index is the race arbiter; see the ABC docstring, SC-3/SC-4).
        for vmid in range(pool_start, pool_end + 1):
            if vmid not in used:
                return vmid
        raise NoFreeVmidError(f"no free VMID in [{pool_start}, {pool_end}]")

    async def usedVmids(self) -> set[int]:
        # Node-discarded projection: the pre-clone reservation scan only needs the
        # in-pool VMID set, so a row with a parseable in-range vmid counts even if
        # its `node` is absent (a malformed/heterogeneous row, WR-04). Kept distinct
        # from listManagedCts (which REQUIRES a node) so a missing node never drops
        # a VMID from the duplicate-id guard.
        resources = await asyncio.to_thread(lambda: self._api.cluster.resources.get(type="vm"))
        start, end = self._settings.worker_pool_start, self._settings.worker_pool_end
        out: set[int] = set()
        for r in resources:
            vmid = self._parse_pool_vmid(r, start, end)
            if vmid is not None:
                out.add(vmid)
        return out

    async def listManagedCts(self) -> list[tuple[str, int]]:
        # CR-01: keep each CT's REAL node (cluster/resources is cluster-wide, so an
        # orphan can live on any node). A row missing/blank `node` is skipped — the
        # reaper cannot safely issue a DELETE without a target node, so it must not
        # claim to manage a CT whose node it does not know.
        resources = await asyncio.to_thread(lambda: self._api.cluster.resources.get(type="vm"))
        start, end = self._settings.worker_pool_start, self._settings.worker_pool_end
        out: list[tuple[str, int]] = []
        for r in resources:
            vmid = self._parse_pool_vmid(r, start, end)
            node = r.get("node")
            if vmid is not None and node:
                out.append((str(node), vmid))
        return out

    @staticmethod
    def _parse_pool_vmid(row: dict[str, Any], start: int, end: int) -> int | None:
        """Parse a cluster/resources row's in-pool VMID, or None if unusable.

        WR-04: cluster/resources rows are heterogeneous — a row may carry `vmid`
        present but non-numeric/None (storage, sdn, or a future resource type
        reusing the key). int() on that raises ValueError/TypeError, which is NOT a
        ComputeError and would escape the seam as an uncaught 500 during the
        pre-clone scan. Returns None for an absent/unparseable/out-of-pool vmid.
        """
        raw = row.get("vmid")
        if raw is None:
            return None
        try:
            vmid = int(raw)
        except (TypeError, ValueError):
            return None
        return vmid if start <= vmid <= end else None

    # ── lifecycle mutations (each UPID-blocked) ───────────────────────────────
    async def cloneCt(
        self,
        template_vmid: int,
        new_vmid: int,
        name: str,
        node: str,
        full: bool = True,
    ) -> ComputeTask:
        def _clone() -> str:
            upid: str = (
                self._api.nodes(node)
                .lxc(template_vmid)
                .clone.post(
                    newid=new_vmid,
                    hostname=name,
                    full=1 if full else 0,
                )
            )
            return upid

        def _configure() -> None:
            # ADR-0003: pool-scoped token must add the new VMID to /pool/burrow-workers.
            self._api.pools(_WORKER_POOL).put(vms=str(new_vmid))
            # ADR-0004: set the static net0 IP from the VMID.
            self._api.nodes(node).lxc(new_vmid).config.put(net0=self._net0_for(new_vmid))

        # Issue the clone POST and capture its UPID.
        try:
            upid = await asyncio.to_thread(_clone)
        except (TaskFailedError, NoFreeVmidError, CloneError):
            raise
        except Exception as exc:  # proxmoxer ResourceException etc. — no driver type escapes
            raise CloneError(f"clone of {template_vmid}->{new_vmid} failed: {exc}") from exc

        # WR-05: block on the clone UPID to completion (exitstatus == OK) BEFORE the
        # dependent pool-add and net0 PUTs. The old order fired those mutations
        # against a half-baked VMID while the clone was still running, so a clone
        # that later failed left a partial CT that had already been pool-added and
        # net0-configured — widening the orphan window compensation must clean up.
        task = await self._block(upid, timeout=self._settings.clone_timeout)

        # Clone confirmed complete: now configure the fully-cloned CT.
        try:
            await asyncio.to_thread(_configure)
        except Exception as exc:  # no driver type escapes the seam
            raise CloneError(f"post-clone configuration of {new_vmid} failed: {exc}") from exc
        return task

    async def injectBootConfig(self, vmid: int, config: BootConfig) -> None:
        # Pull-at-boot (ADR-0002): the worker FETCHES its boot intent from the control
        # plane at boot — nothing is pushed into the CT. The v1 create saga does NOT
        # call this; it persists/checkpoints the intent via the DbProvider directly
        # (see WorkspaceService._persist_boot_intent, WR-03). This provider method is
        # retained as the contract seam for a future push-based backend and is a no-op
        # here (the provider holds no DB handle).
        return None

    async def startCt(self, node: str, vmid: int) -> ComputeTask:
        try:
            upid = await asyncio.to_thread(
                lambda: self._api.nodes(node).lxc(vmid).status.start.post()
            )
        except Exception as exc:
            raise LxcNotReadyError(f"start of {vmid} failed: {exc}") from exc
        return await self._block(upid, timeout=self._settings.task_timeout)

    async def stopCt(self, node: str, vmid: int) -> ComputeTask:
        try:
            upid = await asyncio.to_thread(
                lambda: self._api.nodes(node).lxc(vmid).status.stop.post()
            )
        except Exception as exc:
            raise LxcNotReadyError(f"stop of {vmid} failed: {exc}") from exc
        return await self._block(upid, timeout=self._settings.task_timeout)

    async def destroyCt(self, node: str, vmid: int) -> ComputeTask:
        # Idempotent compensation (Pitfall 7 + CR-03): destroying a nonexistent CT
        # is a no-op success, AND a *running* CT (which Proxmox refuses to DELETE)
        # is stopped first and then destroyed — so a half-started clone the saga
        # produced is still torn down and its VMID freed, never left orphaned.
        try:
            upid = await asyncio.to_thread(lambda: self._api.nodes(node).lxc(vmid).delete())
        except Exception as exc:
            if _is_not_found(exc):
                return ComputeTask(upid=None, status="ok", exitstatus="OK")
            if not _is_running_or_locked(exc):
                raise LxcNotReadyError(f"destroy of {vmid} failed: {exc}") from exc
            # CR-03: the CT is running/locked. Stop it (UPID-blocked) then retry the
            # destroy so compensation actually removes the orphan and frees the VMID.
            await self._force_stop(node, vmid)
            try:
                upid = await asyncio.to_thread(lambda: self._api.nodes(node).lxc(vmid).delete())
            except Exception as retry_exc:
                if _is_not_found(retry_exc):
                    return ComputeTask(upid=None, status="ok", exitstatus="OK")
                raise LxcNotReadyError(
                    f"destroy of {vmid} failed after stop: {retry_exc}"
                ) from retry_exc
        return await self._block(upid, timeout=self._settings.task_timeout)

    async def _force_stop(self, node: str, vmid: int) -> None:
        """Stop a running CT and block on the UPID, tolerating an already-gone CT.

        Used by :meth:`destroyCt` to clear a running/locked CT before a retry of the
        DELETE (CR-03). A 404 here means the CT vanished between the failed delete
        and the stop — treated as success so destroy stays idempotent.
        """
        try:
            upid = await asyncio.to_thread(
                lambda: self._api.nodes(node).lxc(vmid).status.stop.post()
            )
        except Exception as exc:
            if _is_not_found(exc):
                return
            raise LxcNotReadyError(f"stop-before-destroy of {vmid} failed: {exc}") from exc
        await self._block(upid, timeout=self._settings.task_timeout)

    # ── reads ─────────────────────────────────────────────────────────────────
    async def getStatus(self, node: str, vmid: int) -> ComputeStatus:
        try:
            status = await asyncio.to_thread(
                lambda: self._api.nodes(node).lxc(vmid).status.current.get()
            )
        except Exception as exc:
            raise LxcNotReadyError(f"status of {vmid} failed: {exc}") from exc
        return ComputeStatus(
            status=str(status.get("status", "unknown")),
            uptime=int(status.get("uptime", 0)),
            mem=int(status.get("mem", 0)),
            maxmem=int(status.get("maxmem", 0)),
            cpu=float(status.get("cpu", 0.0)),
        )

    async def getIp(self, node: str, vmid: int) -> str | None:
        # Computed from the VMID (ADR-0004, SC-6) — no interface/agent poll.
        return self._ip_for(vmid)

    async def getNodeMemory(self, node: str) -> float:
        status = await asyncio.to_thread(lambda: self._api.nodes(node).status.get())
        mem, maxmem = status["mem"], status["maxmem"]
        return mem / maxmem if maxmem else 1.0

    async def waitTask(self, node: str, upid: str, timeout: float) -> ComputeTask:
        return await self._block(upid, timeout)

    async def healthcheck(self) -> bool:
        try:
            await asyncio.to_thread(lambda: self._api.version.get())
            return True
        except Exception:
            return False

    # ── setup validation (read-only, ephemeral client) ────────────────────────
    async def testConnection(
        self, host: str, user: str, token_name: str, token_value: str
    ) -> ConnectionResult:
        # SETUP-07: validate the operator-TYPED token (not yet in `.env`) with an
        # EPHEMERAL throwaway client built from the passed creds — NEVER self._api.
        # The client goes out of scope at method end; the token is never stored,
        # returned, or logged. CA-pinned TLS still applies (never disabled).
        eph = proxmoxer.ProxmoxAPI(
            host,
            user=user,
            token_name=token_name,
            token_value=token_value,
            verify_ssl=self._settings.proxmox_ca_cert_path,
        )
        try:
            # The ONLY call: a read-only GET /access/permissions returning the
            # privsep token's EFFECTIVE (user ∩ token) permission map. Creates
            # zero resources (SETUP-01).
            perms = await asyncio.to_thread(lambda: eph.access.permissions.get())
        except Exception as exc:
            # FIXED token-free messages — the raw proxmoxer exception string is
            # never interpolated (it can embed auth context; SETUP-07).
            if _is_auth_error(exc):
                raise SetupAuthError("proxmox token was rejected (auth failed)") from None
            raise SetupUnreachableError("proxmox host was unreachable") from None
        present = _flatten_privileges(perms)
        missing = REQUIRED_PRIVS - present
        return ConnectionResult(success=not missing, missing_privileges=sorted(missing))

    async def verifyTemplate(self, template_vmid: int, node: str) -> TemplateResult:
        # SETUP-02: read-only template GET on the runtime client. exists = the GET
        # resolved a config; usable = it exists AND is a template (the `template`
        # flag is truthy). Not found → exists/usable False. Mutates nothing.
        try:
            config = await asyncio.to_thread(
                lambda: self._api.nodes(node).lxc(template_vmid).config.get()
            )
        except Exception as exc:
            # FIXED token-free messages: the raw proxmoxer exception string is
            # never interpolated (it can embed auth context; SETUP-07). Mirrors
            # testConnection's triage: a 404 is "not found" (200 with exists=False),
            # a 401/403 is an auth rejection (SetupAuthError), and only a genuine
            # transport/connect failure is SetupUnreachableError (WR-01). Without the
            # _is_auth_error branch a rejected runtime token surfaced as "host
            # unreachable", sending the operator chasing a network problem.
            if _is_not_found(exc):
                return TemplateResult(
                    exists=False, usable=False, vmid=template_vmid, node=node
                )
            if _is_auth_error(exc):
                raise SetupAuthError("proxmox token was rejected (auth failed)") from None
            raise SetupUnreachableError("proxmox host was unreachable") from None
        usable = bool(config.get("template"))
        return TemplateResult(exists=True, usable=usable, vmid=template_vmid, node=node)


def _flatten_privileges(perms: Any) -> set[str]:
    """Flatten a proxmoxer ``/access/permissions`` map into the set of priv names.

    The response is a ``path -> {priv: 1}`` map (effective permissions across all
    paths the token has rights on). We union the privilege names whose value is
    truthy across every path — the BurrowProvisioner privs are granted at the
    pool/storage/node paths, so a present priv at ANY relevant path counts.
    """
    present: set[str] = set()
    if isinstance(perms, dict):
        for privs in perms.values():
            if isinstance(privs, dict):
                present.update(name for name, granted in privs.items() if granted)
    return present


def _is_auth_error(exc: Exception) -> bool:
    """True when a proxmoxer error indicates the token was rejected (401/403).

    Inspected defensively by status code / message (like ``_is_not_found``) so no
    driver exception type crosses the seam. Distinguishes an auth rejection (→
    SetupAuthError) from a transport/connect failure (→ SetupUnreachableError).
    """
    status_code = getattr(exc, "status_code", None)
    if status_code in (401, 403):
        return True
    text = str(exc).lower()
    return (
        "401" in text
        or "403" in text
        or "authentication failure" in text
        or "permission denied" in text
        or "no ticket" in text
        or "invalid token" in text
    )


def _is_not_found(exc: Exception) -> bool:
    """True when a proxmoxer error indicates the CT no longer exists (404).

    Kept module-private (not a proxmoxer type across the seam): a destroy of an
    already-absent CT must read as idempotent success, so we inspect the error's
    status code / message defensively rather than importing the driver exception type.
    """
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True
    text = str(exc).lower()
    return "does not exist" in text or "not found" in text


def _is_running_or_locked(exc: Exception) -> bool:
    """True when a destroy failed because the CT is running or transiently locked.

    Proxmox refuses to DELETE a running LXC (and a clone can leave one in a locked
    transient state); the error is NOT a 404, so without this discriminator
    ``destroyCt`` would wrongly surface it as a hard failure and leak the VMID
    (CR-03). Inspected defensively by message/status so no driver exception type
    crosses the seam.
    """
    text = str(exc).lower()
    return (
        "running" in text
        or "is locked" in text
        or "lock" in text
        or "can't lock" in text
        or "not stopped" in text
    )
