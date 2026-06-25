# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Structured JSON logging (PLAT-04, Assumption A1).

A single :class:`JsonFormatter` emits each log record as ONE line of JSON so the
backend's stdout is machine-parseable (PLAT-04). It is built on the stdlib
``logging`` module — no new runtime dependency (KISS; the lockfile stays clean,
T-01-SC).

Secret hygiene (ASVS V7, T-01-14): the formatter emits ONLY a fixed set of record
fields plus a *whitelist* of ``extra`` keys. A credential, a Proxmox token, or a
repo URL with embedded userinfo is never an allowed ``extra`` key, so it cannot
reach a log line via this formatter. Callers that must log request context attach
only whitelisted keys (``vmid``, ``repo``, ``workspace_id``, ``status``, ``event``,
``method``, ``path``, ``request_id``); anything else is dropped, not serialized.
"""

import json
import logging
import sys
from datetime import datetime, timezone

# The ONLY ``extra`` keys the formatter is allowed to serialize. Anything outside
# this set is silently dropped so a secret-shaped extra can never reach stdout.
_ALLOWED_EXTRA_KEYS: frozenset[str] = frozenset(
    {
        "vmid",
        "repo",
        "workspace_id",
        "status",
        "event",
        "method",
        "path",
        "request_id",
        # IN-03: auto-select no-fit diagnostics — non-secret by construction (node
        # names + memory fractions, and the numeric capacity threshold).
        "considered",
        "threshold",
    }
)

# Attributes always present on a ``LogRecord``; used to detect caller-supplied
# ``extra`` keys (a record attribute not in this set was passed as ``extra=``).
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Format a ``LogRecord`` as a single JSON line ``{ts, level, logger, msg, ...}``.

    Only whitelisted ``extra`` keys (:data:`_ALLOWED_EXTRA_KEYS`) are appended, so
    no secret-shaped value reaches the log stream. The message is rendered via the
    record's args; the exception type (not a raw traceback with internals) is added
    when present.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS:
                continue
            if key in _ALLOWED_EXTRA_KEYS:
                payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Install the :class:`JsonFormatter` on a stdout handler at the root logger.

    Idempotent: re-running it replaces the handler set rather than stacking
    duplicates (so the app factory may call it on every ``create_app``). uvicorn's
    own loggers are routed through the same handler by clearing their handlers and
    letting them propagate to the root, so server access/error lines are JSON too.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Route uvicorn's loggers through the root handler (JSON), no duplicate lines.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # SETUP-07 (token-in-logs defense): pin the synchronous proxmoxer driver and its
    # requests/urllib3 transport to WARNING so they cannot echo the Authorization
    # header / token at DEBUG. Idempotent — re-running setup_logging re-applies the
    # levels (it never stacks handlers).
    for name in ("proxmoxer", "urllib3", "requests"):
        logging.getLogger(name).setLevel(logging.WARNING)


__all__ = ["JsonFormatter", "setup_logging"]
