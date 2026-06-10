# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""E2E test package (Phase 2 — the phase e2e gate).

Holds the standalone, protocol-accurate stub ttyd server that backs the Playwright
journey over ``BURROW_COMPUTE=fake``. Unlike the in-process pytest fixture in
``tests/integration/conftest.py`` (one event loop, ephemeral port), this server runs
as its OWN process the running bridge can dial at the Fake worker's IP:7681 — so the
real ``tty`` handshake + frame relay is exercised end-to-end in the e2e stack.
"""
