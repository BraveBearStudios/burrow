# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared pytest fixtures for the Phase-0 unit suite.

Everything here is hermetic: the Fake compute provider is in-memory and the
SQLite provider runs the real ``001_init.sql`` migration against a per-test
``tmp_path`` file. No network, no Proxmox, no sleeps. The ``client`` fixture
wires :func:`main.create_app` to an ``httpx.ASGITransport`` so Phase-1 router
tests can hit the app in-process without a live server.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from main import create_app


@dataclass
class _DbSettings:
    """Minimal settings stand-in: ``SqliteProvider`` only reads ``database_path``."""

    database_path: str


@pytest.fixture
def fake_compute() -> FakeComputeProvider:
    """A fresh in-memory, deterministic compute provider per test."""
    return FakeComputeProvider()


@pytest.fixture
async def sqlite_db(tmp_path: Path) -> SqliteProvider:
    """A :class:`SqliteProvider` over a migrated temp DB file (hermetic)."""
    db_path = tmp_path / "burrow-test.db"
    provider = SqliteProvider(_DbSettings(database_path=str(db_path)))
    await provider.migrate()
    return provider


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """An ``httpx.AsyncClient`` bound to the app via ASGI transport (Phase-1 use)."""
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
