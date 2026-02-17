"""
Unit tests for utility functions.
"""

from datetime import datetime, timedelta
from utils import (
    format_price,
    sanitize_url,
    calculate_uptime,
    format_uptime,
    truncate_string,
    validate_webhook_url,
    batch_items,
)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_format_price_simple(self):
        """Test simple price formatting."""
        assert format_price(19.99, "$") == "$19.99"
        assert format_price(5.00, "£") == "£5.00"

    def test_format_price_thousands(self):
        """Test price formatting with thousands separator."""
        assert format_price(1234.56, "$") == "$1,234.56"
        assert format_price(12345.67, "£") == "£12,345.67"

    def test_sanitize_url(self):
        """Test URL sanitization."""
        assert (
            sanitize_url("https://example.com/product?id=123#top")
            == "https://example.com/product"
        )
        assert sanitize_url("https://example.com/page") == "https://example.com/page"

    def test_calculate_uptime(self):
        """Test uptime calculation."""
        start_time = datetime.now() - timedelta(days=1, hours=2, minutes=30, seconds=45)
        uptime = calculate_uptime(start_time)

        assert uptime["days"] == 1
        assert uptime["hours"] == 2
        assert uptime["minutes"] == 30
        # Seconds might vary slightly
        assert 40 <= uptime["seconds"] <= 50

    def test_format_uptime(self):
        """Test uptime formatting."""
        uptime = {"days": 1, "hours": 2, "minutes": 30, "seconds": 45}
        result = format_uptime(uptime)
        assert result == "1d 2h 30m 45s"

    def test_format_uptime_no_days(self):
        """Test uptime formatting without days."""
        uptime = {"days": 0, "hours": 2, "minutes": 30, "seconds": 45}
        result = format_uptime(uptime)
        assert result == "2h 30m 45s"

    def test_format_uptime_seconds_only(self):
        """Test uptime formatting with only seconds."""
        uptime = {"days": 0, "hours": 0, "minutes": 0, "seconds": 45}
        result = format_uptime(uptime)
        assert result == "45s"

    def test_truncate_string_short(self):
        """Test string truncation with short string."""
        result = truncate_string("Short", 10)
        assert result == "Short"

    def test_truncate_string_long(self):
        """Test string truncation with long string."""
        result = truncate_string("This is a very long string", 15)
        assert result == "This is a ve..."
        assert len(result) == 15

    def test_truncate_string_custom_suffix(self):
        """Test string truncation with custom suffix."""
        result = truncate_string("This is a very long string", 15, "…")
        assert result == "This is a very…"
        assert len(result) == 15

    def test_validate_webhook_url_discord_valid(self):
        """Test Discord webhook URL validation - valid."""
        assert validate_webhook_url("https://discord.com/api/webhooks/123/abc") is True
        assert (
            validate_webhook_url("https://discordapp.com/api/webhooks/123/abc") is True
        )

    def test_validate_webhook_url_invalid(self):
        """Test Discord webhook URL validation - invalid."""
        assert validate_webhook_url("https://example.com") is False
        assert validate_webhook_url("https://discord.com") is False

    def test_batch_items(self):
        """Test item batching."""
        items = [1, 2, 3, 4, 5, 6, 7]
        batches = batch_items(items, 3)

        assert len(batches) == 3
        assert batches[0] == [1, 2, 3]
        assert batches[1] == [4, 5, 6]
        assert batches[2] == [7]

    def test_batch_items_exact_fit(self):
        """Test item batching with exact fit."""
        items = [1, 2, 3, 4, 5, 6]
        batches = batch_items(items, 2)

        assert len(batches) == 3
        assert batches[0] == [1, 2]
        assert batches[1] == [3, 4]
        assert batches[2] == [5, 6]

    def test_batch_items_single_batch(self):
        """Test item batching with single batch."""
        items = [1, 2, 3]
        batches = batch_items(items, 10)

        assert len(batches) == 1
        assert batches[0] == [1, 2, 3]

    def test_batch_items_empty(self):
        """Test item batching with empty list."""
        items = []
        batches = batch_items(items, 5)

        assert len(batches) == 0

    def test_get_file_size(self):
        """Test get_file_size function."""
        import tempfile
        from utils import get_file_size

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World" * 100)
            temp_path = f.name

        try:
            size = get_file_size(temp_path)
            assert "B" in size or "KB" in size
        finally:
            import os

            os.unlink(temp_path)

    def test_get_file_size_not_found(self):
        """Test get_file_size with non-existent file."""
        from utils import get_file_size

        result = get_file_size("/nonexistent/file.txt")
        assert result == "File not found"

    def test_health_check_database(self):
        """Test database health check."""
        from utils import HealthCheck
        from database import Database
        from config.config import Database as DatabaseConfig

        config = DatabaseConfig(engine="sqlite", name="test_health")
        db = Database(config)

        try:
            is_healthy, error = HealthCheck.check_database(db)
            assert is_healthy is True
            assert error is None
        finally:
            db.engine.dispose()

    def test_health_check_database_failure(self):
        """Test database health check with failure."""
        from utils import HealthCheck
        from unittest.mock import Mock

        mock_db = Mock()
        mock_db.get_statistics.side_effect = Exception("Database error")

        is_healthy, error = HealthCheck.check_database(mock_db)
        assert is_healthy is False
        assert error is not None

    def test_health_check_messengers(self):
        """Test messenger health check."""
        from utils import HealthCheck
        from unittest.mock import Mock

        mock_messenger1 = Mock()
        mock_messenger1.name = "discord1"
        mock_messenger1.active = True

        mock_messenger2 = Mock()
        mock_messenger2.name = "telegram1"
        mock_messenger2.active = False

        mock_messengers = Mock()
        mock_messengers.all_messengers = [mock_messenger1, mock_messenger2]

        status = HealthCheck.check_messengers(mock_messengers)
        assert status["discord1"] is True
        assert status["telegram1"] is False

    def test_health_check_stockists(self):
        """Test stockist health check."""
        from utils import HealthCheck
        from unittest.mock import Mock

        mock_stockist1 = Mock()
        mock_stockist1.name = "bestbuy.com"

        mock_stockist2 = Mock()
        mock_stockist2.name = "gamestop.com"

        mock_stockists = Mock()
        mock_stockists.all_stockists = [mock_stockist1, mock_stockist2]

        status = HealthCheck.check_stockists(mock_stockists)
        assert status["bestbuy.com"] is True
        assert status["gamestop.com"] is True

    def test_get_system_info(self):
        """Test get_system_info function."""
        from utils import HealthCheck

        info = HealthCheck.get_system_info()
        assert "python_version" in info
        assert "platform" in info
        assert "processor" in info

    def test_format_price_zero(self):
        """Test price formatting with zero."""
        assert format_price(0.0, "$") == "$0.00"

    def test_format_price_negative(self):
        """Test price formatting with negative value."""
        assert format_price(-19.99, "$") == "$-19.99"

    def test_sanitize_url_already_clean(self):
        """Test URL sanitization with already clean URL."""
        assert (
            sanitize_url("https://example.com/product") == "https://example.com/product"
        )

    def test_truncate_string_exact_length(self):
        """Test string truncation at exact length."""
        result = truncate_string("12345", 5)
        assert result == "12345"

    def test_validate_webhook_url_with_path(self):
        """Test webhook URL validation with full path."""
        assert (
            validate_webhook_url("https://discord.com/api/webhooks/123456789/abcdefg")
            is True
        )
        assert (
            validate_webhook_url("https://discordapp.com/api/webhooks/123/abc") is True
        )
