# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""DB-first credential resolution for the GUI-managed store (ADR-0015).

Resolves the GitHub credential and the Proxmox token, preferring a GUI-set value in
the encrypted store over the ``.env`` bootstrap value, so an operator can rotate a
credential from the UI without editing ``.env`` or restarting. Store ciphertext is
decrypted at the :mod:`lib.secretBox` boundary; plaintext is never persisted.

Precedence (both credentials): encrypted store -> ``.env`` -> (git only) a clearly
non-production DEV-PLACEHOLDER. The Fernet key is read lazily, so a deployment with
no store configured (empty ``BURROW_SECRET_KEY``) never builds a ``SecretBox`` just
to fall back to ``.env``.
"""

import logging

from config import Settings
from db.provider import DbProvider
from lib.secretBox import DecryptionError, EnvSecretKeyProvider, SecretBox, SecretKeyError

# The non-production marker returned when no git credential is configured anywhere.
GIT_PLACEHOLDER_PREFIX = "DEV-PLACEHOLDER-NOT-A-REAL-CREDENTIAL"

# Only non-secret context (never a credential value) ever reaches this logger.
logger = logging.getLogger("burrow.credentials")


class CredentialResolver:
    """Resolve credentials DB-first, falling back to ``.env`` (ADR-0015)."""

    def __init__(self, db: DbProvider, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    def _box(self) -> SecretBox:
        # Built lazily and only when there is ciphertext to decrypt, so an
        # unconfigured deployment (empty BURROW_SECRET_KEY) is never forced to carry
        # a key just to fall back to .env.
        key = self._settings.burrow_secret_key.get_secret_value()
        return SecretBox(EnvSecretKeyProvider(key))

    async def git_credential(self, repo: str) -> str:
        """Return the git credential for a boot fetch (store -> ``.env`` -> placeholder)."""
        enc = await self._db.getCredentialCiphertext("git_token")
        if enc is not None:
            try:
                return self._box().decrypt(enc)
            except (SecretKeyError, DecryptionError):
                # A credential IS stored but the key cannot decrypt it. Fall through to
                # the .env value / placeholder so a key problem does not 500 every
                # worker boot; log LOUDLY (never the value).
                logger.error(
                    "a GitHub credential is stored but could not be decrypted "
                    "(BURROW_SECRET_KEY missing or changed); falling back to .env"
                )
        token = self._settings.git_credential_token
        if token:
            return token
        return f"{GIT_PLACEHOLDER_PREFIX}:{repo}"

    async def proxmox_token(self) -> str | None:
        """Return a GUI-set Proxmox token, or ``None`` to fall back to the ``.env`` value."""
        enc = await self._db.getCredentialCiphertext("proxmox_token")
        if enc is not None:
            try:
                return self._box().decrypt(enc)
            except (SecretKeyError, DecryptionError):
                # Same posture as git: an undecryptable stored token falls back to .env
                # (None signals "use .env"); logged loudly, never silently masked.
                logger.error(
                    "a Proxmox token is stored but could not be decrypted "
                    "(BURROW_SECRET_KEY missing or changed); falling back to the .env token"
                )
        return None
