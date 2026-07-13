# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Persistence provider seam (PLAT-06).

``DbProvider`` is the abstract contract every persistence backend implements
(tech-spec §6.3 + a ``healthcheck`` for ``/health`` forward-compat). Every method
is ``async`` and returns a Pydantic DTO from :mod:`models` (or ``None``) — no
driver type or raw row ever leaks past this interface.

Implementations:

- :class:`db.sqliteProvider.SqliteProvider` — the SQLite-backed v1 self-host store
  over ``001_init.sql``.
- :class:`db.postgresProvider.PostgresProvider` — hosted-path stub.

Driver symbols stay confined to the concrete impl files (seam-leakage
discipline); this ABC names none of them.
"""

from abc import ABC, abstractmethod
from typing import Any

from models.event import WorkspaceEvent
from models.template import Template
from models.workspace import Workspace


class VmidTakenError(Exception):
    """Raised when a workspace INSERT collides on the active-vmid unique index.

    The DB-seam analogue of "lost the VMID race": the ``002`` partial unique
    index (``WHERE deletedAt IS NULL``) is the cross-process reservation arbiter
    (SC-3/SC-4), so a duplicate-active-vmid INSERT surfaces here. Declared on the
    ABC module so the service can catch it ("collision → retry the scan") without
    importing the ``aiosqlite`` driver — preserving the seam.
    """


class DbProvider(ABC):
    """Abstract persistence backend (SQLite or Postgres).

    Cannot be instantiated directly. The concrete impl is chosen once in the app
    factory from ``settings`` (``BURROW_DB=sqlite``); services depend on this ABC,
    never on an impl.
    """

    @abstractmethod
    async def createWorkspace(self, data: dict[str, Any]) -> Workspace:
        """Insert a workspace row and return the created :class:`Workspace`."""
        ...

    @abstractmethod
    async def getWorkspace(self, workspaceId: str) -> Workspace | None:
        """Return the workspace by id, or ``None``; excludes soft-deleted rows."""
        ...

    @abstractmethod
    async def listWorkspaces(self, status: str | None = None) -> list[Workspace]:
        """Return workspaces, optionally filtered by status; excludes soft-deleted."""
        ...

    @abstractmethod
    async def updateWorkspace(self, workspaceId: str, updates: dict[str, Any]) -> Workspace:
        """Apply ``updates`` to a workspace and return the updated row."""
        ...

    @abstractmethod
    async def softDeleteWorkspace(self, workspaceId: str) -> None:
        """Soft-delete a workspace (set ``deletedAt``); the row is retained for audit."""
        ...

    @abstractmethod
    async def logEvent(self, workspaceId: str, eventType: str, data: dict[str, Any]) -> None:
        """Append an event row for a workspace."""
        ...

    @abstractmethod
    async def getEvents(self, workspaceId: str) -> list[WorkspaceEvent]:
        """Return a workspace's event log oldest-first (WS-11)."""
        ...

    @abstractmethod
    async def getByVmid(self, vmid: int) -> Workspace | None:
        """Return the active workspace owning ``vmid``, or ``None``.

        Excludes soft-deleted rows so a recycled vmid resolves to the live owner
        (feeds the bootconfig router + saga compensation lookups).
        """
        ...

    @abstractmethod
    async def listTemplates(self) -> list[Template]:
        """Return the seeded golden templates (feeds ``GET /api/v1/templates``)."""
        ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Return ``True`` when the store is reachable (cheap ``SELECT 1``, PLAT-03)."""
        ...

    @abstractmethod
    async def getSetupState(self) -> dict[str, Any]:
        """Return the singleton setup-state row (``id=1``), READ-ONLY.

        Reads ``settings.setupCompletedAt`` (``003`` migration; seeded ``NULL``)
        as ``{"setupCompletedAt": <iso str | None>}``. The setter is
        :meth:`setSetupCompleted` (Phase 13).
        """
        ...

    @abstractmethod
    async def setSetupCompleted(self) -> dict[str, Any]:
        """Stamp the singleton settings row's ``setupCompletedAt`` to now (SETUP-05).

        Writes the current ISO-8601 UTC time onto the ``id=1`` settings row and
        returns the same ``{"setupCompletedAt": <iso str>}`` shape
        :meth:`getSetupState` returns. Idempotent in effect: re-stamping a valid
        singleton never fails (no INSERT, no uniqueness to violate), so a second
        call simply re-writes the timestamp on the existing row (ADR-0011).
        """
        ...

    # ── Credential store (ADR-0015) ───────────────────────────────────────

    @abstractmethod
    async def setCredentials(self, updates: dict[str, Any]) -> None:
        """Persist encrypted credential ciphertext + last4 for the provided fields.

        ``updates`` may carry ``proxmox_token_enc``/``proxmox_token_last4`` and/or
        ``git_token_enc``/``git_token_last4``; only the provided keys are written, so a
        partial update touches one credential without clearing the other. Always
        stamps ``credentialsUpdatedAt``. The ciphertext is produced by the caller
        (``lib.secretBox``); no plaintext secret ever crosses this seam (ADR-0015).
        """
        ...

    @abstractmethod
    async def getCredentialStatus(self) -> dict[str, Any]:
        """Return credential status ONLY — never a stored value (ADR-0015 / SETUP-07).

        ``{proxmoxTokenSet, proxmoxTokenLast4, gitTokenSet, gitTokenLast4,
        updatedAt}``. Ciphertext is never returned here; this feeds the write-only
        ``GET /setup/credentials`` status endpoint.
        """
        ...

    @abstractmethod
    async def getCredentialCiphertext(self, key: str) -> bytes | None:
        """Return the stored ciphertext for ``key`` (``proxmox_token``/``git_token``).

        Returns the opaque Fernet token bytes (or ``None`` when unset) for the caller
        to decrypt at the ``lib.secretBox`` boundary. Ciphertext is safe to cross the
        seam; the plaintext is recovered only inside the service, never persisted.
        """
        ...

    @abstractmethod
    async def setAdminSecret(self, secret_hash: str) -> None:
        """Store the argon2id hash of the credential-surface admin secret (ADR-0015).

        The caller hashes the secret (``argon2``); this persists the opaque hash only.
        The plaintext admin secret is never stored or returned.
        """
        ...

    @abstractmethod
    async def getAdminSecretHash(self) -> str | None:
        """Return the stored argon2id admin-secret hash, or ``None`` when unset.

        The caller verifies a presented secret against it; the provider stays
        crypto-free (no ``argon2`` import here).
        """
        ...

    @abstractmethod
    async def writeAudit(
        self,
        action: str,
        outcome: str,
        *,
        target: str | None = None,
        source_ip: str | None = None,
        detail: str | None = None,
    ) -> None:
        """Append an immutable ``audit_log`` row (SOC 2 CC7.2/CC7.3).

        Records ``action`` + ``outcome`` (plus optional non-secret ``target``,
        ``source_ip``, ``detail``) with an auto-stamped ``createdAt``. NEVER pass a
        secret value in any field.
        """
        ...

    @abstractmethod
    async def listAudit(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent ``audit_log`` rows newest-first, up to ``limit`` (CRED-05).

        Each dict carries the non-secret audit fields with camelCase keys
        (``id, action, target, outcome, sourceIp, detail, createdAt``). The rows never
        contain a secret value by construction (``writeAudit`` forbids it), so this
        read is safe to surface behind the admin-gated status endpoint. READ-ONLY.
        """
        ...
