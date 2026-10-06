"""
Unit tests for structured logging.
"""

import io
import json
import logging
import sys
from datetime import datetime, timezone

from utils import JSONFormatter


class TestJSONFormatter:
    """Test JSONFormatter structured log output."""

    def _format_record(self, message="test message", level=logging.INFO, **extra):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        for key, value in extra.items():
            record.__dict__[key] = value
        return json.loads(formatter.format(record))

    def test_emits_valid_json(self):
        data = self._format_record()
        assert isinstance(data, dict)

    def test_has_core_fields(self):
        data = self._format_record()
        assert "ts" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "test message"

    def test_timestamp_is_iso_format(self):
        data = self._format_record()
        assert "T" in data["ts"]
        assert data["ts"].endswith("Z")

    def test_timestamp_is_real_utc_with_milliseconds(self, monkeypatch):
        import time

        # Non-UTC zone: the old local-time-with-Z output would be 1 hour out.
        monkeypatch.setenv("TZ", "Europe/London")
        time.tzset()
        try:
            created = datetime(
                2026, 10, 6, 18, 53, 38, 123000, tzinfo=timezone.utc
            ).timestamp()
            formatter = JSONFormatter()
            record = logging.LogRecord(
                name="t",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="m",
                args=(),
                exc_info=None,
            )
            record.created = created
            data = json.loads(formatter.format(record))
            assert data["ts"] == "2026-10-06T18:53:38.123Z"
        finally:
            monkeypatch.undo()
            time.tzset()

    def test_traceback_included(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("kaboom")
        except ValueError:
            record = logging.LogRecord(
                name="t",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        data = json.loads(formatter.format(record))
        assert "Traceback (most recent call last)" in data["exc_info"]
        assert "ValueError: kaboom" in data["exc_info"]

    def test_preset_exc_text_is_honoured(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=None,
        )
        record.exc_text = "pre-rendered traceback"
        data = json.loads(formatter.format(record))
        assert data["exc_info"] == "pre-rendered traceback"

    def test_stack_info_included(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="m",
            args=(),
            exc_info=None,
        )
        record.stack_info = "Stack (most recent call last):\n  frame"
        data = json.loads(formatter.format(record))
        assert data["stack_info"].startswith("Stack (most recent call last)")

    def test_no_exc_keys_without_exception(self):
        data = self._format_record()
        assert "exc_info" not in data
        assert "stack_info" not in data

    def test_non_serialisable_extra_still_logs(self):
        data = self._format_record(obj=object(), path=__import__("pathlib").Path("/x"))
        assert data["message"] == "test message"
        assert data["path"] == "/x"
        assert data["obj"].startswith("<object object")

    def test_extra_fields_included(self):
        data = self._format_record(stockist="bestbuy.com", duration_ms=42)
        assert data["stockist"] == "bestbuy.com"
        assert data["duration_ms"] == 42

    def test_message_with_args_interpolated(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="Stockist %s failed",
            args=("cexuk",),
            exc_info=None,
        )
        data = json.loads(formatter.format(record))
        assert data["message"] == "Stockist cexuk failed"
        assert data["level"] == "WARNING"

    def test_error_level_included(self):
        data = self._format_record(level=logging.ERROR)
        assert data["level"] == "ERROR"

    def test_redaction_applies_before_json_format(self):
        import logging.handlers

        from amiibot import SecretRedactionFilter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        handler.addFilter(SecretRedactionFilter())

        logger = logging.getLogger("test.redaction")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.info("Bot token bot123456:secret_token_here")
        logger.removeHandler(handler)

        line = stream.getvalue().strip().splitlines()[0]
        data = json.loads(line)
        assert "secret_token_here" not in data["message"]
        assert "***" in data["message"]


class TestRedactionEndToEnd:
    def _logger(self, formatter):
        from amiibot import SecretRedactionFilter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)
        handler.addFilter(SecretRedactionFilter())
        logger = logging.getLogger("test.redaction.e2e")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)
        return logger, handler, stream

    def test_secret_in_exception_arg_traceback_and_extra(self):
        secret_url = "https://discord.com/api/webhooks/123/secretToken123"
        logger, handler, stream = self._logger(JSONFormatter())
        try:
            try:
                raise RuntimeError(f"POST {secret_url} failed")
            except RuntimeError as e:
                logger.error(
                    "Delivery failed: %s",
                    e,
                    exc_info=True,
                    extra={"target": secret_url},
                )
        finally:
            logger.removeHandler(handler)

        raw = stream.getvalue()
        assert "secretToken123" not in raw
        data = json.loads(raw.strip())
        assert "Traceback" in data["exc_info"]
        assert data["target"].endswith("webhooks/123/***")

    def test_console_formatter_redacts_traceback(self):
        secret_url = "https://discord.com/api/webhooks/123/secretToken123"
        logger, handler, stream = self._logger(logging.Formatter("%(message)s"))
        try:
            try:
                raise RuntimeError(secret_url)
            except RuntimeError:
                logger.error("Failed", exc_info=True)
        finally:
            logger.removeHandler(handler)

        out = stream.getvalue()
        assert "RuntimeError" in out
        assert "secretToken123" not in out


class TestSetupLogging:
    def test_file_handler_uses_json_formatter(self):
        from amiibot import setup_logging

        setup_logging()
        handlers = logging.getLogger().handlers
        file_handler = next(
            h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert isinstance(file_handler.formatter, JSONFormatter)

    def test_console_handler_human_readable_by_default(self):
        from amiibot import setup_logging

        setup_logging()
        handlers = logging.getLogger().handlers
        console_handler = next(
            h
            for h in handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert not isinstance(console_handler.formatter, JSONFormatter)

    def test_console_handler_json_with_flag(self):
        from amiibot import setup_logging

        setup_logging(log_json=True)
        handlers = logging.getLogger().handlers
        console_handler = next(
            h
            for h in handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert isinstance(console_handler.formatter, JSONFormatter)

    def test_handlers_have_secret_redaction_filter(self):
        from amiibot import SecretRedactionFilter, setup_logging

        setup_logging()
        for handler in logging.getLogger().handlers:
            filters = [
                f for f in handler.filters if isinstance(f, SecretRedactionFilter)
            ]
            assert len(filters) >= 1
