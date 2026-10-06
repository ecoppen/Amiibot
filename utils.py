"""Logging helpers for Amiibot."""

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Emits keys ``ts`` (ISO8601 UTC timestamp with milliseconds), ``level``,
    ``logger`` and ``message``. ``exc_info`` and ``stack_info`` are included
    as formatted strings when present. Any extra fields passed via the
    ``extra`` keyword of a log call are included, with values that are not
    JSON serialisable converted using ``str``.
    """

    _SKIPPED_KEYS = frozenset(
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
            "message",
        }
    )

    # Keys that are never treated as extras. Shared with SecretRedactionFilter.
    SKIPPED_KEYS = _SKIPPED_KEYS

    def format(self, record: logging.LogRecord) -> str:
        created = datetime.fromtimestamp(record.created, tz=timezone.utc)
        data: dict[str, Any] = {
            "ts": created.strftime("%Y-%m-%dT%H:%M:%S.")
            + f"{created.microsecond // 1000:03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in data and key not in self._SKIPPED_KEYS:
                data[key] = value
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            data["exc_info"] = record.exc_text
        if record.stack_info:
            data["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(data, default=str)
