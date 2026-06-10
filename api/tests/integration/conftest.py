# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration-tier fixtures: ASGITransport over real SQLite + Fake compute + stub ttyd.

The ``integration_client`` fixture builds the real app (``create_app``) bound to an
``httpx.ASGITransport`` and drives it in-process — no live server. The app runs over:

- the **Fake** compute provider (``BURROW_COMPUTE=fake``, the shipped hermetic impl), and
- a **real** temp-SQLite DB (``settings.database_path`` pointed at ``tmp_path``), so the
  001+002 migrations actually run (exercises Plan 01).

The create saga's step-6 ttyd health GET is a real ``httpx`` call against the Fake's
VMID-derived IP (``10.99.0.<vmid>``). ``respx`` mocks that one httpx leg, returning 200
for ``http://10.99.0.*:7681/`` so ``_wait_ttyd`` resolves — the protocol-accurate
stub-ttyd for this tier (the tty subprotocol bridge is Phase 2). ``respx`` is the right
tool here: the ttyd leg is httpx, and proxmoxer (requests-based) is not involved over
the Fake.
"""

import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import respx

from config import settings

# The Fake derives a worker IP from the VMID (10.99.0.<vmid % 256>); the stub ttyd
# answers the health GET on :7681 for any address in that range.
_TTYD_URL_PATTERN = re.compile(r"http://10\.99\.0\.\d+:7681/")


@pytest.fixture
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the shared settings at a temp DB + a known non-* CORS origin.

    ``get_db`` constructs a fresh ``SqliteProvider`` per request from
    ``settings.database_path``, so overriding it on the singleton is sufficient to
    isolate each test to its own migrated DB file. ``monkeypatch`` restores the
    originals at teardown.
    """
    monkeypatch.setattr(settings, "compute", "fake", raising=False)
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "burrow-int.db"), raising=False)
    monkeypatch.setattr(settings, "allowed_origin", "http://burrow-ui.lan:5173", raising=False)


@pytest.fixture
def stub_ttyd() -> Iterator[respx.MockRouter]:
    """Mock the httpx ttyd-health GET so the create/start saga resolves (200)."""
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=_TTYD_URL_PATTERN.pattern).mock(return_value=httpx.Response(200))
        yield router


@pytest.fixture
async def integration_client(
    _isolated_settings: None, stub_ttyd: respx.MockRouter
) -> AsyncIterator[httpx.AsyncClient]:
    """An ``httpx.AsyncClient`` bound to the real app over temp SQLite + Fake + stub ttyd."""
    # Import here so the settings overrides above are in effect when the app builds.
    from main import create_app, reset_compute

    # Fresh Fake compute per test: drop the process-wide singleton so no container
    # or VMID leaks from a prior test (the DB is already per-test via tmp_path).
    reset_compute()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
