# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""WR-01: the mint_repo_credential dev-placeholder seam (A3).

v1 does NOT mint a real short-lived, per-repo-scoped credential — the seam is a
pluggable placeholder pending the operator's A3 decision. These tests pin the v1
contract so the code and its docstring no longer disagree:

- with no token configured, the returned value is an explicitly non-production,
  DEV-PLACEHOLDER-marked string (never mistakable for a real credential);
- when a global ``git_credential_token`` IS configured, it is returned verbatim
  (the stopgap), AND a structured warning is emitted so the "not actually
  repo-scoped" reality is visible — WITHOUT ever logging the token value itself.
"""

import logging
from dataclasses import dataclass

import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from services.workspaceService import WorkspaceService


@dataclass
class _Settings:
    """Minimal settings stub carrying only what mint_repo_credential reads."""

    git_credential_token: str = ""
    database_path: str = ":memory:"


def _service(token: str = "") -> WorkspaceService:
    settings = _Settings(git_credential_token=token)
    return WorkspaceService(
        compute=FakeComputeProvider(),
        db=SqliteProvider(settings),
        settings=settings,  # type: ignore[arg-type]
    )


async def test_placeholder_is_clearly_non_production() -> None:
    """No token configured → a DEV-PLACEHOLDER string, never a real-looking cred."""
    cred = await _service(token="").mint_repo_credential("git@example.com:acme/app.git")
    assert cred == "DEV-PLACEHOLDER-NOT-A-REAL-CREDENTIAL:git@example.com:acme/app.git"
    # The marker makes a leak obvious and the value is not credential-shaped.
    assert "PLACEHOLDER" in cred


async def test_global_token_is_served_but_warns_without_leaking_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A configured global token is returned verbatim AND warned about (no value leak)."""
    secret = "ghp_globaltokennotrepo_scoped_0123456789"
    service = _service(token=secret)

    with caplog.at_level(logging.WARNING, logger="burrow.workspace"):
        cred = await service.mint_repo_credential("git@example.com:acme/app.git")

    # The stopgap value is returned (so the boot path works today)…
    assert cred == secret

    # …a warning was emitted flagging the global non-repo-scoped stopgap…
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "expected a structured warning when serving the global token"
    assert any("non-repo-scoped" in r.getMessage() for r in warnings)

    # …and the token VALUE never appears in any log record (message or extra).
    for record in caplog.records:
        assert secret not in record.getMessage(), "token value leaked into the warning message"
        for value in record.__dict__.values():
            assert secret not in str(value), "token value leaked into a log extra"
