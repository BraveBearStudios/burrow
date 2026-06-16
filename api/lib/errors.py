# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Service-tier typed errors (WS-09, CAP-01, SC-12).

These are the policy-layer exceptions ``WorkspaceService`` raises. Each carries a
stable ``.code`` string so the Plan-04 router maps ``error.code`` deterministically
onto the envelope error shape (:func:`lib.envelope.respond_error`) without a
fragile ``isinstance`` ladder. They are deliberately driver-free: catching them
never requires importing ``aiosqlite`` or ``proxmoxer`` (seam discipline).

Messages are operator-facing and MUST NOT carry secrets or internals (ASVS V7);
the saga's ``_safe`` redactor governs what reaches event ``data``.
"""


class ServiceError(Exception):
    """Base class for service-tier errors that map to an envelope error code.

    The ``.code`` attribute is the stable wire code the router emits; subclasses
    set it as a class attribute so ``error.code`` is invariant across instances.

    ``safe_message`` is an OPTIONAL, author-curated operator-facing string the
    router may surface verbatim. It is ONLY ever set to vetted, wire-safe literals
    (never raw ``str(exc)``, never user/topology/secret data) so the no-leak
    contract (ASVS V7, T-01-14) holds: when it is ``None`` the router falls back to
    the static ``_SAFE_ERROR_MESSAGES`` table keyed by ``.code``. The diagnostic
    ``str(exc)`` is kept for logs and is never surfaced.
    """

    code: str = "service_error"
    safe_message: str | None = None


class IllegalTransitionError(ServiceError):
    """A lifecycle action is not legal from the workspace's current state (WS-09)."""

    code = "illegal_transition"

    def __init__(self, state: str, action: str) -> None:
        self.state = state
        self.action = action
        super().__init__(f"illegal transition: cannot {action!r} from state {state!r}")


class CapacityError(ServiceError):
    """A node is over the capacity threshold; create is refused (CAP-01, WSX-01).

    Two refusal shapes share the one ``capacity_exceeded`` code:

    - the operator-selected node is over threshold (manual path) -> the default
      message names that node (``CapacityError(node)``) and carries NO
      ``safe_message``, so the router emits the static
      "The selected node is over capacity." — correct for the manual path, and
    - auto-select found NO fitting node -> a curated ``message=`` doubles as the
      ``safe_message`` the router surfaces verbatim, carrying the manual-pick hint
      (``CapacityError(message=…)``).

    ``message`` is keyword-only and additive: existing single-arg
    ``CapacityError(node)`` callers are unchanged, and ``.code`` is invariant. When
    supplied, ``message`` is an AUTHOR-CURATED literal (no untrusted/secret data),
    so promoting it to ``safe_message`` keeps the no-leak contract (ASVS V7).
    """

    code = "capacity_exceeded"

    def __init__(self, node: str | None = None, *, message: str | None = None) -> None:
        self.node = node
        if message is not None:
            # Curated literal: safe to surface verbatim at the wire boundary.
            self.safe_message = message
            super().__init__(message)
        else:
            super().__init__(f"node {node!r} is over the capacity threshold")


class NoFreeVmidError(ServiceError):
    """No free VMID could be reserved in the worker pool (WS-10).

    Service-level analogue of the compute seam's ``NoFreeVmidError``: raised when
    the bounded reservation-retry loop exhausts the pool. Kept distinct from the
    compute error so the service can attach the policy ``.code`` the router maps,
    rather than re-exporting a driver-adjacent type.
    """

    code = "no_free_vmid"

    def __init__(self, message: str = "no free VMID in the worker pool") -> None:
        super().__init__(message)


class WorkspaceBootError(ServiceError):
    """A workspace failed to reach a healthy running state during the saga (WS-03)."""

    code = "boot_failed"


class WorkspaceNotFoundError(ServiceError):
    """No active workspace exists for the requested id (WS-05/06/07/08)."""

    code = "not_found"

    def __init__(self, workspace_id: str) -> None:
        self.workspace_id = workspace_id
        super().__init__(f"workspace {workspace_id!r} not found")


class IllegalVmidError(ServiceError):
    """A bootconfig request named a vmid outside the worker pool (WORK-03, T-01-17).

    Raised by the bootconfig router when ``vmid`` falls outside
    ``[worker_pool_start, worker_pool_end]``. The router maps it to a 404 whose
    operator-facing message is a generic "not found" — the probed value is held on
    ``.vmid`` for triage but MUST NOT be echoed into the envelope (enumeration
    resistance, ASVS V4/V5). It is distinct from ``WorkspaceNotFoundError`` (which
    is keyed by a string id) so the out-of-pool probe and the no-active-workspace
    case can be reasoned about separately while presenting the same wire shape.
    """

    code = "illegal_vmid"

    def __init__(self, vmid: int) -> None:
        self.vmid = vmid
        # Message is for internal triage only; the router never echoes it (T-01-17).
        super().__init__("vmid out of pool range")
