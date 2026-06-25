# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compute provider seam (PLAT-07, SC-13).

``ComputeProvider`` is the abstract contract every compute backend implements.
It exposes the complete method set the Phase-1 create/stop/start/destroy sagas
will call, so the contract is frozen before the saga is written. Every method is
``async`` and returns a Pydantic DTO from :mod:`models.compute` (or a plain
``int``/``set``/``bool``/``str``) — no driver type (``proxmoxer``,
``ProxmoxAPI``) ever leaks past this interface.

Implementations:

- :class:`compute.fakeProvider.FakeComputeProvider` — in-memory, deterministic
  (hermetic test substrate, PLAT-08).
- :class:`compute.proxmoxProvider.ProxmoxComputeProvider` — Phase-1 skeleton.

Errors are a typed hierarchy (:class:`ComputeError` and subclasses); routers
(Phase 1) map these to envelope error codes.
"""

from abc import ABC, abstractmethod

from models.compute import (
    BootConfig,
    ComputeStatus,
    ComputeTask,
    ConnectionResult,
    TemplateResult,
)


class ComputeError(Exception):
    """Base class for all compute-seam errors."""


class NoFreeVmidError(ComputeError):
    """No free VMID remains in the requested pool range."""


class CloneError(ComputeError):
    """A container clone operation failed."""


class TaskFailedError(ComputeError):
    """A Proxmox UPID task finished in a non-OK state."""


class LxcNotReadyError(ComputeError):
    """A container is not in the expected ready state for the operation."""


class SetupUnreachableError(ComputeError):
    """The Proxmox host/network was unreachable during setup validation.

    Carries a FIXED, token-free message: no raw driver exception string (which
    can embed auth context) is interpolated, so the operator-typed token cannot
    leak through the error (SETUP-07).
    """


class SetupAuthError(ComputeError):
    """The token was rejected during setup validation (401/403).

    Carries a FIXED, token-free message (SETUP-07): the raw proxmoxer exception
    string is never interpolated, so the rejected token never reaches an envelope
    or log line.
    """


class ComputeProvider(ABC):
    """Abstract compute backend (Proxmox or Fake).

    Cannot be instantiated directly. The concrete impl is chosen once in the app
    factory from ``settings`` (``BURROW_COMPUTE=fake|proxmox``); services depend
    on this ABC, never on an impl.
    """

    @abstractmethod
    async def getNextVmid(self, pool_start: int, pool_end: int, used: set[int]) -> int:
        """Return the first free VMID in ``[pool_start, pool_end]`` not in ``used``.

        Raises :class:`NoFreeVmidError` when the range is exhausted.

        .. warning::
           This is a *pure computation* over the ``used`` snapshot the caller
           passes; it does NOT reserve the returned VMID. ``usedVmids()`` →
           ``getNextVmid()`` → ``cloneCt()`` is a read-then-act sequence with no
           reservation in between, so two concurrent create sagas can pick the
           same free VMID. Atomic reservation is provided ONLY by the Phase-1 DB
           insert under the partial unique index on ``workspaces.vmid``
           (``WHERE deletedAt IS NULL``, WS-10 / SC-4). Callers MUST reserve the
           VMID via that insert *before* ``cloneCt`` and treat a uniqueness
           violation as "lost the race, retry" — never rely on this method for
           race-safety on its own. (The Fake masks the race: it is
           single-threaded and stateful, so saga tests pass while a real
           provider would collide.)
        """
        ...

    @abstractmethod
    async def usedVmids(self) -> set[int]:
        """Return the set of VMIDs the compute backend currently knows about.

        This is a point-in-time snapshot with no lock. See
        :meth:`getNextVmid` — the snapshot may be stale by the time a clone runs,
        so it is an optimization input, not a reservation. The DB partial unique
        index (WS-10) is the only authority that prevents duplicate live VMIDs.
        """
        ...

    @abstractmethod
    async def listManagedCts(self) -> list[tuple[str, int]]:
        """Return ``(node, vmid)`` for every worker-pool CT the backend knows about.

        Unlike :meth:`usedVmids` (which discards the node), this preserves each
        CT's REAL node so the reaper can destroy an orphan against the node it
        actually lives on (CR-01). The create saga selects an operator node per
        workspace (CAP-04), so a row-less orphan can live on ANY node — destroying
        it against a hardcoded ``default_node`` issues the DELETE to the wrong node,
        which the real provider 404s and swallows as idempotent success, leaking the
        CT and its VMID while the reaper logs a false ``reaper.destroyed``.

        Same point-in-time-snapshot caveat as :meth:`usedVmids`: no lock, the
        reaper re-asserts the pool-range + live-owner bounds over the result.
        """
        ...

    @abstractmethod
    async def cloneCt(
        self,
        template_vmid: int,
        new_vmid: int,
        name: str,
        node: str,
        full: bool = True,
    ) -> ComputeTask:
        """Clone the golden template to ``new_vmid`` (``--full`` by default, SC)."""
        ...

    @abstractmethod
    async def injectBootConfig(self, vmid: int, config: BootConfig) -> None:
        """Persist non-secret boot intent for ``vmid`` (pull-at-boot, SC-4/SC-5).

        This is a DB-write-only seam: the real impl persists the intent the
        worker fetches at boot; it does NOT push files into the CT. The Fake
        no-ops.
        """
        ...

    @abstractmethod
    async def startCt(self, node: str, vmid: int) -> ComputeTask:
        """Start container ``vmid`` on ``node``."""
        ...

    @abstractmethod
    async def stopCt(self, node: str, vmid: int) -> ComputeTask:
        """Stop container ``vmid`` on ``node``."""
        ...

    @abstractmethod
    async def destroyCt(self, node: str, vmid: int) -> ComputeTask:
        """Destroy container ``vmid`` on ``node`` and free its VMID."""
        ...

    @abstractmethod
    async def getStatus(self, node: str, vmid: int) -> ComputeStatus:
        """Return the runtime status of container ``vmid``."""
        ...

    @abstractmethod
    async def getIp(self, node: str, vmid: int) -> str | None:
        """Return the container IP, computed from the VMID (SC-6), not polled."""
        ...

    @abstractmethod
    async def getNodeMemory(self, node: str) -> float:
        """Return the node's used-memory fraction for the capacity guard (CAP-01)."""
        ...

    @abstractmethod
    async def waitTask(self, node: str, upid: str, timeout: float) -> ComputeTask:
        """Block on a Proxmox UPID task until completion or ``timeout`` (SC-1)."""
        ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Return ``True`` when the compute backend is reachable (PLAT-03)."""
        ...

    @abstractmethod
    async def testConnection(
        self, host: str, user: str, token_name: str, token_value: str
    ) -> ConnectionResult:
        """Validate a host/token strictly READ-ONLY and report missing privileges.

        Asserts the BurrowProvisioner privilege set is present via the privsep
        token's EFFECTIVE permissions (a single read-only probe) and creates ZERO
        resources (SETUP-01). The Proxmox impl builds an EPHEMERAL throwaway client
        from these exact request-body creds (never the runtime ``self._api``),
        issues one GET, and discards it.

        ``token_value`` is transient request-body input: it is NEVER persisted,
        returned in any envelope, or written to a log line (SETUP-07). No driver
        type (``proxmoxer``/``ProxmoxAPI``) crosses this interface; auth/connect
        failures surface as :class:`SetupAuthError` / :class:`SetupUnreachableError`
        with fixed token-free messages.
        """
        ...

    @abstractmethod
    async def verifyTemplate(self, template_vmid: int, node: str) -> TemplateResult:
        """Report whether the golden template exists and is usable, READ-ONLY.

        Issues template GETs only and mutates NOTHING (SETUP-02): ``exists`` =
        the template VMID resolved on ``node``; ``usable`` = it exists AND is a
        template. No driver type crosses this interface.
        """
        ...
