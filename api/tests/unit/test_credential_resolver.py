# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""DB-first credential resolution contract (ADR-0015).

Over a REAL ``SqliteProvider`` on a ``tmp_path`` DB, locks that the
``CredentialResolver`` prefers a GUI-set value in the encrypted store over the
``.env`` bootstrap:

- ``git_credential``: nothing configured -> DEV-PLACEHOLDER; ``.env`` set -> the
  ``.env`` token; store set -> the decrypted store value, overriding ``.env``;
- ``proxmox_token``: unset -> ``None`` (the caller falls back to ``.env``); store
  set -> the decrypted token.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from db.sqliteProvider import SqliteProvider
from lib.credentialResolver import CredentialResolver
from lib.secretBox import EnvSecretKeyProvider, SecretBox, generate_key


@dataclass
class _Settings:
    """Settings stub carrying exactly what the resolver reads."""

    database_path: str
    git_credential_token: str = ""
    burrow_secret_key: SecretStr = SecretStr("")


def _resolver(
    tmp_path: Path, *, git_env: str = "", key: str = ""
) -> tuple[CredentialResolver, SqliteProvider, SecretBox | None]:
    settings = _Settings(
        database_path=str(tmp_path / "res.db"),
        git_credential_token=git_env,
        burrow_secret_key=SecretStr(key),
    )
    db = SqliteProvider(settings)
    box = SecretBox(EnvSecretKeyProvider(key)) if key else None
    return CredentialResolver(db, settings), db, box  # type: ignore[arg-type]


async def test_git_placeholder_when_nothing_configured(tmp_path: Path) -> None:
    resolver, _, _ = _resolver(tmp_path)
    cred = await resolver.git_credential("git@example.com:acme/app.git")
    assert cred == "DEV-PLACEHOLDER-NOT-A-REAL-CREDENTIAL:git@example.com:acme/app.git"


async def test_git_env_used_when_no_store(tmp_path: Path) -> None:
    resolver, _, _ = _resolver(tmp_path, git_env="ghp_env_stopgap_value")
    assert await resolver.git_credential("repo") == "ghp_env_stopgap_value"


async def test_git_store_overrides_env(tmp_path: Path) -> None:
    key = generate_key()
    resolver, db, box = _resolver(tmp_path, git_env="ghp_env_stopgap_value", key=key)
    assert box is not None
    await db.setCredentials(
        {"git_token_enc": box.encrypt("ghp_GUI_set_pat"), "git_token_last4": "_pat"}
    )
    # The GUI-set store value wins over the .env stopgap.
    assert await resolver.git_credential("repo") == "ghp_GUI_set_pat"


async def test_proxmox_none_when_unset_then_store_value(tmp_path: Path) -> None:
    key = generate_key()
    resolver, db, box = _resolver(tmp_path, key=key)
    assert box is not None
    assert await resolver.proxmox_token() is None  # caller falls back to .env
    await db.setCredentials(
        {"proxmox_token_enc": box.encrypt("pve-token-xyz"), "proxmox_token_last4": "-xyz"}
    )
    assert await resolver.proxmox_token() == "pve-token-xyz"


async def test_git_decrypt_failure_falls_back_to_env(tmp_path: Path) -> None:
    # A git credential is stored under `key`, but a resolver with the WRONG key reads it:
    # decrypt fails -> the resolver must fall back to the .env value, not raise (ADR-0015
    # hardening: a key problem cannot 500 every worker boot).
    key = generate_key()
    _, db, box = _resolver(tmp_path, git_env="ghp_env_fallback_value", key=key)
    assert box is not None
    await db.setCredentials(
        {"git_token_enc": box.encrypt("ghp_stored_value"), "git_token_last4": "alue"}
    )
    wrong_key_resolver, _, _ = _resolver(
        tmp_path, git_env="ghp_env_fallback_value", key=generate_key()
    )
    assert await wrong_key_resolver.git_credential("repo") == "ghp_env_fallback_value"
