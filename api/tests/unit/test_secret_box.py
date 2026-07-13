# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Fernet credential SecretBox + key provider (ADR-0015).

Locks the encryption contract the at-rest credential store depends on:
- encrypt -> decrypt round-trips the plaintext, and the stored form is ciphertext;
- a different key cannot decrypt (wrong-key fails closed);
- tampered ciphertext fails closed;
- a missing or malformed ``BURROW_SECRET_KEY`` fails fast with ``SecretKeyError``
  and never leaks the key material.
"""

import pytest

from lib.secretBox import (
    DecryptionError,
    EnvSecretKeyProvider,
    SecretBox,
    SecretKeyError,
    generate_key,
)


def _box(key: str) -> SecretBox:
    return SecretBox(EnvSecretKeyProvider(key))


def test_encrypt_decrypt_round_trips() -> None:
    box = _box(generate_key())
    token = box.encrypt("glpat-secret-pat-value")
    assert token != b"glpat-secret-pat-value"  # at rest it is ciphertext, not plaintext
    assert box.decrypt(token) == "glpat-secret-pat-value"


def test_wrong_key_cannot_decrypt() -> None:
    token = _box(generate_key()).encrypt("s3cret")
    other = _box(generate_key())
    with pytest.raises(DecryptionError):
        other.decrypt(token)


def test_tampered_ciphertext_fails_closed() -> None:
    box = _box(generate_key())
    token = bytearray(box.encrypt("s3cret"))
    token[-1] ^= 0x01  # flip one byte of the authentication tag
    with pytest.raises(DecryptionError):
        box.decrypt(bytes(token))


def test_missing_key_fails_fast() -> None:
    with pytest.raises(SecretKeyError):
        _box("").encrypt("s3cret")


def test_malformed_key_fails_fast_without_leaking() -> None:
    box = _box("not-a-valid-fernet-key")
    with pytest.raises(SecretKeyError) as excinfo:
        box.encrypt("s3cret")
    assert "not-a-valid-fernet-key" not in str(excinfo.value)
