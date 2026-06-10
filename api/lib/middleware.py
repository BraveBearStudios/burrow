# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Security-headers middleware (PLAT-05, RESEARCH Pattern 7).

:class:`SecurityHeadersMiddleware` sets a fixed set of defensive response headers
on EVERY response (success or error) at the ASGI boundary — applied once here, not
per-route (T-01-13). The headers are appropriate for an API-only, LAN-deployed
service:

- ``X-Content-Type-Options: nosniff`` — no MIME sniffing.
- ``X-Frame-Options: DENY`` — never framed (clickjacking defense).
- ``Referrer-Policy: no-referrer`` — never leak the request URL on navigation.
- ``Content-Security-Policy: default-src 'none'`` — an API serves no HTML; deny all
  subresource loads by default.

HSTS is deliberately OMITTED: v1 is a plain-HTTP LAN app (nginx terminates TLS
upstream, not the API), so advertising ``Strict-Transport-Security`` here would be
misleading (RESEARCH Pattern 7).
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# The fixed header set applied to every response (no HSTS — LAN HTTP app).
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the fixed security-header set to every response (PLAT-05)."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


__all__ = ["SecurityHeadersMiddleware"]
