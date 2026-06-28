# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fernet credential encryption-at-rest and the pluggable key provider (ADR-0015).

The GUI-managed credential store keeps the Proxmox API token and the GitHub PAT
encrypted at rest. Encryption is Fernet (AES-128-CBC with an HMAC-SHA256
authentication tag) from ``cryptography``; plaintext exists only transiently in
memory at the encrypt call and at the proxmoxer / git boundary on decrypt.

The Fernet key is resolved through a ``SecretKeyProvider`` so the self-host path
(key in ``.env`` via ``EnvSecretKeyProvider``) and a future hosted path (a KMS
provider) are interchangeable behind one seam, mirroring the ``DbProvider`` and
``ComputeProvider`` discipline. ``cryptography`` is confined to this module.
"""

from abc import ABC, abstractmethod

from cryptography.fernet import Fernet, InvalidToken


class SecretKeyError(RuntimeError):
    """No usable Fernet key is configured (ADR-0015 fail-fast).

    Raised when the credential store is exercised but ``BURROW_SECRET_KEY`` is unset
    or is not a valid Fernet key. The message is generic and never echoes the key.
    """


class DecryptionError(RuntimeError):
    """Stored ciphertext could not be decrypted (wrong key or tampered data).

    Maps to a fixed token-free error at the endpoint; the message names no secret.
    """


class SecretKeyProvider(ABC):
    """Resolves the symmetric Fernet key used to encrypt credentials at rest."""

    @abstractmethod
    def getKey(self) -> bytes:
        """Return the urlsafe-base64 Fernet key as bytes, or raise ``SecretKeyError``."""


class EnvSecretKeyProvider(SecretKeyProvider):
    """Reads the Fernet key from configuration (``BURROW_SECRET_KEY``, self-host).

    The key lives in the gitignored ``.env`` only and is never written to the DB
    (ADR-0015). An empty value raises ``SecretKeyError`` so an enabled store never
    runs without a key.
    """

    def __init__(self, key: str) -> None:
        self._key = key

    def getKey(self) -> bytes:
        if not self._key:
            raise SecretKeyError(
                "BURROW_SECRET_KEY is not set; the credential store requires a Fernet key"
            )
        return self._key.encode("utf-8")


class SecretBox:
    """Encrypt and decrypt credential plaintext with the provider's Fernet key."""

    def __init__(self, key_provider: SecretKeyProvider) -> None:
        self._key_provider = key_provider

    def _fernet(self) -> Fernet:
        try:
            return Fernet(self._key_provider.getKey())
        except (ValueError, TypeError) as exc:
            # A malformed BURROW_SECRET_KEY (not 32 urlsafe-base64 bytes). Never echo
            # the key material — surface a generic fail-fast instead.
            raise SecretKeyError("BURROW_SECRET_KEY is not a valid Fernet key") from exc

    def encrypt(self, plaintext: str) -> bytes:
        """Return Fernet ciphertext for ``plaintext`` (a credential value)."""
        return self._fernet().encrypt(plaintext.encode("utf-8"))

    def decrypt(self, token: bytes) -> str:
        """Return the plaintext for stored ``token``, or raise ``DecryptionError``."""
        try:
            return self._fernet().decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise DecryptionError(
                "credential decryption failed (wrong key or tampered ciphertext)"
            ) from exc


def generate_key() -> str:
    """Return a fresh urlsafe-base64 Fernet key (onboarding key generation, tests)."""
    return Fernet.generate_key().decode("utf-8")
