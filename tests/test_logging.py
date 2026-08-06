"""
Unit tests for structured logging.
"""

import io
import json
import logging

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
