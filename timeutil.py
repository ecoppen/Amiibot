"""Time helpers. The app works in timezone-aware UTC throughout."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(UTC)
