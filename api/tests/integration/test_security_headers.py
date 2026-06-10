# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: security headers + non-* CORS + no-secrets-in-logs (PLAT-04/05).

block_on=high asserts (RESEARCH Security Domain):

- every response carries the four security headers (X-Content-Type-Options,
  X-Frame-Options, Referrer-Policy, Content-Security-Policy) — applied at the ASGI
  boundary for success AND error responses (PLAT-05, T-01-13);
- a CORS preflight from the configured origin is allowed and the response's
  ``access-control-allow-origin`` is the non-* configured origin, never ``*`` (PLAT-05);
- a sentinel secret passed as a non-whitelisted ``extra`` never reaches a JSON log
  line — the ``JsonFormatter`` field whitelist drops it (PLAT-04, T-01-14).
"""

import json
import logging

import httpx

from config import settings
from lib.logging import JsonFormatter

_SECURITY_HEADERS = (
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "content-security-policy",
)


async def test_headers_present_on_success(integration_client: httpx.AsyncClient) -> None:
    """A successful response carries every security header; HSTS is absent."""
    response = await integration_client.get("/api/v1/health")
    assert response.status_code == 200
    for header in _SECURITY_HEADERS:
        assert header in response.headers, f"missing security header: {header}"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == "default-src 'none'"
    # LAN HTTP app: HSTS must NOT be advertised.
    assert "strict-transport-security" not in response.headers


async def test_headers_present_on_error(integration_client: httpx.AsyncClient) -> None:
    """An error response (404) still carries the security headers (T-01-13)."""
    response = await integration_client.get("/api/v1/workspaces/missing")
    assert response.status_code == 404
    for header in _SECURITY_HEADERS:
        assert header in response.headers, f"missing security header on error: {header}"


async def test_cors_allows_configured_origin_not_wildcard(
    integration_client: httpx.AsyncClient,
) -> None:
    """A preflight from the configured origin is allowed; the ACAO is non-* (PLAT-05)."""
    origin = settings.allowed_origin
    assert origin != "*"

    response = await integration_client.options(
        "/api/v1/workspaces",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    acao = response.headers.get("access-control-allow-origin")
    assert acao == origin
    assert acao != "*"


def test_sentinel_secret_never_reaches_json_log() -> None:
    """A non-whitelisted secret extra is dropped by the JsonFormatter (PLAT-04, block_on=high)."""
    sentinel = "ghp_SENTINELsecretTOKENvalue000000000000"
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="bootconfig",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="bootconfig.issued",
        args=(),
        exc_info=None,
    )
    # Attach the secret as a non-whitelisted extra (as a careless caller might).
    record.git_credential = sentinel
    record.repo = "git@example.com:acme/alpha.git"  # whitelisted, allowed

    line = formatter.format(record)
    parsed = json.loads(line)  # one valid JSON line

    assert sentinel not in line, "secret leaked into the JSON log line"
    assert "git_credential" not in parsed
    assert parsed["repo"] == "git@example.com:acme/alpha.git"  # whitelisted survives
    assert parsed["msg"] == "bootconfig.issued"
