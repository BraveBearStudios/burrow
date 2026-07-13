# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Argon2 admin-gate hashing contract (ADR-0015).

Locks the credential-surface gate's hashing primitive:
- hash -> verify round-trips, and the stored form is an argon2id hash, not plaintext;
- a wrong secret fails closed (False, never raises);
- a malformed stored hash fails closed (False, never raises).
"""

from lib.adminGate import hash_admin_secret, verify_admin_secret


def test_hash_verify_round_trip() -> None:
    secret = "correct horse battery staple"
    stored = hash_admin_secret(secret)
    assert stored != secret  # at rest it is a hash, not the plaintext
    assert stored.startswith("$argon2id$")
    assert verify_admin_secret(secret, stored) is True


def test_wrong_secret_fails_closed() -> None:
    stored = hash_admin_secret("right-secret-value")
    assert verify_admin_secret("wrong-secret-value", stored) is False


def test_malformed_hash_fails_closed() -> None:
    # A corrupt/foreign stored hash must return False, never raise (fail-closed).
    assert verify_admin_secret("anything", "not-a-valid-argon2-hash") is False
