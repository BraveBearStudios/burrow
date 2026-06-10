# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Response envelope helper (PLAT-02).

Every API response is shaped as ``{data, meta:{requestId, timestamp}, error}``.
This is a pure boundary helper: it carries no router or service logic. Routers
call :func:`respond` for the success shape and :func:`respond_error` for the
error shape; both attach a fresh :class:`Meta` (``requestId`` + ISO-8601 UTC
``timestamp``).
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel


class Meta(BaseModel):
    """Per-response metadata carried in every envelope."""

    requestId: str
    timestamp: str


class ApiError(BaseModel):
    """The ``error`` payload shape for a failed response."""

    code: str
    message: str


def make_meta(request_id: str | None = None) -> Meta:
    """Build a :class:`Meta`, defaulting ``requestId`` to a fresh UUID and
    ``timestamp`` to the current ISO-8601 UTC time."""
    return Meta(
        requestId=request_id or str(uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def respond(data: Any, request_id: str | None = None) -> dict[str, Any]:
    """Wrap ``data`` in the standard success envelope."""
    return {
        "data": data,
        "meta": make_meta(request_id).model_dump(),
        "error": None,
    }


def respond_error(code: str, message: str, request_id: str | None = None) -> dict[str, Any]:
    """Wrap an error ``code``/``message`` in the standard error envelope."""
    return {
        "data": None,
        "meta": make_meta(request_id).model_dump(),
        "error": ApiError(code=code, message=message).model_dump(),
    }
