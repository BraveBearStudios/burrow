# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local admin gate for the credential surface (ADR-0015).

A single operator admin secret (set during first-run setup) gates the credential
status + write endpoints and the settings screen. The secret is stored ONLY as an
``argon2id`` hash; the plaintext is never persisted, logged, or returned.

This is the self-host access control for the most sensitive surface (the Proxmox
token + GitHub PAT) under v1's LAN-only no-auth posture — NOT per-user identity,
which arrives with the hosted Entra path (ADR-0015 deviation note). ``argon2`` is
confined to this module so the DbProvider stays crypto-free.
"""

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

# Minimum admin-secret length. Modest by design: a self-host LAN operator secret,
# not an internet-facing password. Enforced at the request boundary.
MIN_ADMIN_SECRET_LENGTH = 8

# argon2id with the library defaults (64 MiB / time-cost 3 / parallelism 4): ample
# for an infrequently-verified single-operator gate.
_hasher = PasswordHasher()


def hash_admin_secret(secret: str) -> str:
    """Return an ``argon2id`` hash of ``secret`` (the plaintext is never stored)."""
    return _hasher.hash(secret)


def verify_admin_secret(secret: str, stored_hash: str) -> bool:
    """Return ``True`` iff ``secret`` matches ``stored_hash``; never raises on mismatch.

    A wrong secret, a malformed stored hash, or any argon2 error all return ``False``
    (fail-closed), so the gate can branch on a plain boolean without leaking which
    failure occurred. ``InvalidHashError`` subclasses ``ValueError`` (not
    ``Argon2Error``), so both are caught.
    """
    try:
        return _hasher.verify(stored_hash, secret)
    except (Argon2Error, InvalidHashError):
        return False
