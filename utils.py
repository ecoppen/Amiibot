"""
Utility functions for Amiibot application.

This module provides helper functions for common operations like validation,
formatting, and utility tasks.
"""

import logging
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger(__name__)


def format_price(price: float, currency: str = "$") -> str:
    """Format a price with currency symbol.

    Args:
        price: Numeric price value
        currency: Currency symbol (default: $)

    Returns:
        Formatted price string

    Examples:
        >>> format_price(19.99)
        '$19.99'
        >>> format_price(1234.56, "£")
        '£1,234.56'
    """
    if price >= 1000:
        return f"{currency}{price:,.2f}"
    return f"{currency}{price:.2f}"


def sanitize_url(url: str) -> str:
    """Sanitize a URL by removing query parameters and fragments.

    Args:
        url: Input URL

    Returns:
        Sanitized URL

    Examples:
        >>> sanitize_url("https://example.com/product?id=123#top")
        'https://example.com/product'
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def calculate_uptime(start_time: datetime) -> dict[str, int]:
    """Calculate application uptime.

    Args:
        start_time: Application start timestamp

    Returns:
        Dictionary with days, hours, minutes, seconds

    Examples:
        >>> start = datetime.now() - timedelta(hours=25)
        >>> calculate_uptime(start)
        {'days': 1, 'hours': 1, 'minutes': 0, 'seconds': 0}
    """
    uptime = datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return {"days": days, "hours": hours, "minutes": minutes, "seconds": seconds}


def format_uptime(uptime: dict[str, int]) -> str:
    """Format uptime dictionary as human-readable string.

    Args:
        uptime: Dictionary from calculate_uptime()

    Returns:
        Formatted string

    Examples:
        >>> format_uptime({'days': 1, 'hours': 2, 'minutes': 30, 'seconds': 45})
        '1d 2h 30m 45s'
    """
    parts = []
    if uptime["days"] > 0:
        parts.append(f"{uptime['days']}d")
    if uptime["hours"] > 0:
        parts.append(f"{uptime['hours']}h")
    if uptime["minutes"] > 0:
        parts.append(f"{uptime['minutes']}m")
    parts.append(f"{uptime['seconds']}s")

    return " ".join(parts)


def truncate_string(s: str, max_length: int, suffix: str = "...") -> str:
    """Truncate a string to maximum length.

    Args:
        s: Input string
        max_length: Maximum allowed length
        suffix: Suffix to add if truncated (default: "...")

    Returns:
        Truncated string

    Examples:
        >>> truncate_string("This is a very long string", 15)
        'This is a ve...'
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def validate_webhook_url(url: str) -> bool:
    """Validate if a URL is a valid Discord webhook.

    Args:
        url: URL to validate

    Returns:
        True if valid Discord webhook URL

    Examples:
        >>> validate_webhook_url("https://discord.com/api/webhooks/123/abc")
        True
        >>> validate_webhook_url("https://example.com")
        False
    """
    return "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url


def get_file_size(filepath: str) -> str:
    """Get human-readable file size.

    Args:
        filepath: Path to file

    Returns:
        Formatted file size (e.g., "1.5 MB")

    Examples:
        >>> get_file_size("log.txt")
        '2.3 MB'
    """
    import os

    if not os.path.exists(filepath):
        return "File not found"

    size_bytes: float = float(os.path.getsize(filepath))

    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.1f} TB"


def batch_items(items: list[Any], batch_size: int) -> list[list[Any]]:
    """Split a list into batches of specified size.

    Args:
        items: List to batch
        batch_size: Size of each batch

    Returns:
        List of batched lists

    Examples:
        >>> batch_items([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


class HealthCheck:
    """Application health check utilities."""

    @staticmethod
    def check_database(database: Any) -> tuple[bool, Optional[str]]:
        """Check database connection health.

        Args:
            database: Database instance

        Returns:
            Tuple of (is_healthy, error_message)
        """
        try:
            database.get_statistics()
            return True, None
        except Exception as e:
            log.error(f"Database health check failed: {e}")
            return False, str(e)

    @staticmethod
    def check_messengers(messengers: Any) -> dict[str, bool]:
        """Check messenger health status.

        Args:
            messengers: MessageManager instance

        Returns:
            Dictionary of messenger names to health status
        """
        status = {}
        for messenger in messengers.all_messengers:
            status[messenger.name] = messenger.active
        return status

    @staticmethod
    def check_stockists(stockists: Any) -> dict[str, bool]:
        """Check stockist configuration health.

        Args:
            stockists: StockistManager instance

        Returns:
            Dictionary of stockist names to configuration status
        """
        status = {}
        for stockist in stockists.all_stockists:
            status[stockist.name] = True  # If loaded, it's configured
        return status

    @staticmethod
    def get_system_info() -> dict[str, Any]:
        """Get system information.

        Returns:
            Dictionary with system metrics
        """
        import platform
        import sys

        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
        }
