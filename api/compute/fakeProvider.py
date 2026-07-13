# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""In-memory deterministic compute provider (PLAT-08).

``FakeComputeProvider`` implements the full :class:`ComputeProvider` contract
backed by a ``dict[int, _FakeContainer]``. It is *shipped app code* (selected by
``BURROW_COMPUTE=fake``), not a test double, so the integration and e2e tiers run
hermetically with zero Proxmox.

Determinism guarantees (so saga tests are reproducible):

- No randomness, no sleeps. Every result is a pure function of its inputs and the
  in-memory state.
- ``getIp`` derives the address from the VMID (``10.99.0.<vmid % 256>``), so the
  same ``(node, vmid)`` always yields the same IP.
- The lifecycle (clone -> stopped, start -> running, destroy -> removed) matches
  the real provider's observable effects, so a saga that passes here fails
  against Proxmox only for real-infra (not state-machine) reasons.

Failure injection (for Phase-1 compensation tests): the constructor accepts an
optional :class:`FakeFailures` config that makes a named method raise on its
Nth call. The shape is fixed now so Phase 1 does not refactor the constructor.
"""

from dataclasses import dataclass, field

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
)

# Memory the Fake reports per node: low enough to stay under any capacity guard.
_DEFAULT_NODE_MEMORY = 0.25


@dataclass
class _FakeContainer:
    """In-memory record of a fake container."""

    vmid: int
    name: str
    node: str
    running: bool = False


@dataclass
class FakeFailures:
    """Injectable failure hooks for compensation tests.

    Maps a method name (e.g. ``"startCt"``, ``"getIp"``, ``"cloneCt"``) to the
    1-based call ordinal on which that method should raise. The raised error type
    matches the method's documented failure mode (``CloneError`` for clone,
    ``LxcNotReadyError`` otherwise). Calls are counted per method name across the
    provider's lifetime.

    Setup negative paths (SETUP-01/02, Phase 12) are toggled declaratively so
    BOTH a missing-privileges result and an auth-fail are reachable for the
    wizard's negative tests, plus a template-not-found:

    - ``setup_missing_privileges``: testConnection returns ``success=False`` with
      these missing privilege names.
    - ``setup_auth_fails``: testConnection raises :class:`SetupAuthError`.
    - ``setup_template_missing``: verifyTemplate returns ``exists=usable=False``.
    """

    raise_on_nth_call: dict[str, int] = field(default_factory=dict)
    setup_missing_privileges: list[str] | None = None
    setup_auth_fails: bool = False
    setup_template_missing: bool = False


class FakeComputeProvider(ComputeProvider):
    """Deterministic, in-memory :class:`ComputeProvider` (PLAT-08)."""

    def __init__(
        self,
        failures: FakeFailures | None = None,
        node_memory: float = _DEFAULT_NODE_MEMORY,
        node_fractions: dict[str, float] | None = None,
    ) -> None:
        self._containers: dict[int, _FakeContainer] = {}
        self._failures = failures or FakeFailures()
        self._node_memory = node_memory
        # Optional per-node used-memory fractions (WSX-01): when a node name is in
        # this dict, getNodeMemory returns its value; otherwise it falls back to the
        # single _node_memory float, so a dict need not enumerate every node. An
        # empty/None dict keeps the single-float behavior (full backward-compat).
        self._node_fractions = node_fractions or {}
        self._call_counts: dict[str, int] = {}

    # ── internal helpers ──────────────────────────────────────────────────
    def _maybe_fail(self, method: str) -> None:
        """Raise the method's failure error if this is its configured Nth call."""
        self._call_counts[method] = self._call_counts.get(method, 0) + 1
        nth = self._failures.raise_on_nth_call.get(method)
        if nth is not None and self._call_counts[method] == nth:
            if method == "cloneCt":
                raise CloneError(f"injected failure on {method} call {nth}")
            raise LxcNotReadyError(f"injected failure on {method} call {nth}")

    @staticmethod
    def _fake_ip(vmid: int) -> str:
        """Deterministic IP derived from the VMID (SC-6)."""
        return f"10.99.0.{vmid % 256}"

    @staticmethod
    def _ok_task() -> ComputeTask:
        return ComputeTask(upid=None, status="ok", exitstatus="OK")

    # ── ComputeProvider contract ──────────────────────────────────────────
    async def getNextVmid(self, pool_start: int, pool_end: int, used: set[int]) -> int:
        self._maybe_fail("getNextVmid")
        taken = used | self._containers.keys()
        for vmid in range(pool_start, pool_end + 1):
            if vmid not in taken:
                return vmid
        raise NoFreeVmidError(f"no free VMID in [{pool_start}, {pool_end}]")

    async def usedVmids(self) -> set[int]:
        self._maybe_fail("usedVmids")
        return set(self._containers.keys())

    async def listManagedCts(self) -> list[tuple[str, int]]:
        # CR-01: surface each container's REAL node so the reaper destroys an
        # orphan on the node it lives on, not a hardcoded default. The Fake stores
        # `node` per container, so the pair is honest.
        self._maybe_fail("listManagedCts")
        return [(c.node, c.vmid) for c in self._containers.values()]

    async def cloneCt(
        self,
        template_vmid: int,
        new_vmid: int,
        name: str,
        node: str,
        full: bool = True,
    ) -> ComputeTask:
        self._maybe_fail("cloneCt")
        if new_vmid in self._containers:
            raise CloneError(f"VMID {new_vmid} already exists")
        self._containers[new_vmid] = _FakeContainer(
            vmid=new_vmid, name=name, node=node, running=False
        )
        return self._ok_task()

    async def injectBootConfig(self, vmid: int, config: BootConfig) -> None:
        # DB-write-only seam (pull-at-boot, SC-4): the Fake has no DB, so it
        # accepts and discards the config.
        self._maybe_fail("injectBootConfig")

    async def startCt(self, node: str, vmid: int) -> ComputeTask:
        self._maybe_fail("startCt")
        container = self._containers.get(vmid)
        if container is None:
            raise LxcNotReadyError(f"VMID {vmid} does not exist")
        container.running = True
        return self._ok_task()

    async def stopCt(self, node: str, vmid: int) -> ComputeTask:
        self._maybe_fail("stopCt")
        container = self._containers.get(vmid)
        if container is None:
            raise LxcNotReadyError(f"VMID {vmid} does not exist")
        container.running = False
        return self._ok_task()

    async def destroyCt(self, node: str, vmid: int) -> ComputeTask:
        self._maybe_fail("destroyCt")
        # CR-01: model the real provider's NODE-SCOPED DELETE honestly. Proxmox
        # routes DELETE to `nodes(node).lxc(vmid)`; a DELETE aimed at the WRONG
        # node 404s, which destroyCt swallows as idempotent success WITHOUT
        # removing the CT that actually lives on another node. The old Fake keyed
        # only on `vmid`, so it removed a container regardless of node and masked a
        # reaper that destroyed against the wrong node (CR-01). Now a wrong-node
        # destroy is the same harmless no-op success the real provider returns —
        # but the container survives, so a misrouted reap is observable in tests.
        container = self._containers.get(vmid)
        if container is None:
            return self._ok_task()  # already gone → idempotent no-op success
        if container.node != node:
            # Wrong-node DELETE → 404 on the real provider, swallowed as success;
            # the CT on its real node is untouched (the exact CR-01 leak).
            return self._ok_task()
        # CR-03: a running CT is stopped first (Proxmox refuses to DELETE a running
        # LXC), then removed — so destroy is idempotent for the cloned-but-running
        # case and always frees the VMID, matching ProxmoxComputeProvider.destroyCt.
        if container.running:
            container.running = False
        self._containers.pop(vmid, None)
        return self._ok_task()

    async def getStatus(self, node: str, vmid: int) -> ComputeStatus:
        self._maybe_fail("getStatus")
        container = self._containers.get(vmid)
        if container is None:
            raise LxcNotReadyError(f"VMID {vmid} does not exist")
        status = "running" if container.running else "stopped"
        uptime = 3600 if container.running else 0
        return ComputeStatus(
            status=status,
            uptime=uptime,
            mem=536_870_912,
            maxmem=2_147_483_648,
            cpu=0.01,
        )

    async def getIp(self, node: str, vmid: int) -> str | None:
        self._maybe_fail("getIp")
        container = self._containers.get(vmid)
        if container is None or not container.running:
            return None
        return self._fake_ip(vmid)

    async def getNodeMemory(self, node: str) -> float:
        self._maybe_fail("getNodeMemory")
        # Per-node fraction when configured; single-float fallback otherwise (WSX-01).
        return self._node_fractions.get(node, self._node_memory)

    async def waitTask(self, node: str, upid: str, timeout: float) -> ComputeTask:
        # Fake tasks are synchronous — no sleep, return OK immediately (SC-1).
        self._maybe_fail("waitTask")
        return self._ok_task()

    async def healthcheck(self) -> bool:
        return True

    # ── setup validation (deterministic parity, injectable negative) ───────
    async def testConnection(
        self, host: str, user: str, token_name: str, token_value: str
    ) -> ConnectionResult:
        # Deterministic success by default (parity with the Proxmox read-only
        # probe); FakeFailures toggles the two negative paths Plan 02 asserts.
        # The token is never stored/returned/logged (SETUP-07) — same as real.
        self._maybe_fail("testConnection")
        if self._failures.setup_auth_fails:
            raise SetupAuthError("proxmox token was rejected (auth failed)")
        missing = self._failures.setup_missing_privileges
        if missing:
            return ConnectionResult(success=False, missing_privileges=sorted(missing))
        return ConnectionResult(success=True, missing_privileges=[])

    async def verifyTemplate(self, template_vmid: int, node: str) -> TemplateResult:
        self._maybe_fail("verifyTemplate")
        if self._failures.setup_template_missing:
            return TemplateResult(exists=False, usable=False, vmid=template_vmid, node=node)
        return TemplateResult(exists=True, usable=True, vmid=template_vmid, node=node)
