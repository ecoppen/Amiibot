"""
Application constants for Amiibot.

Centralized configuration for magic numbers, timeouts, and other constants.
"""

# ============================================================================
# TIMEOUT SETTINGS (in seconds)
# ============================================================================

REQUEST_TIMEOUT = 5
"""Default timeout for HTTP requests."""

SELENIUM_WAIT_MAX = 20
"""Maximum wait time for Selenium WebDriver operations (page load, script, element wait)."""

# ============================================================================
# LOGGING SETTINGS
# ============================================================================

LOG_FILE_NAME = "log.txt"
"""Default log file name."""

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
"""Maximum size of a log file before rotation."""

LOG_BACKUP_COUNT = 5
"""Number of rotated log files to keep."""

# ============================================================================
# MESSAGE SENDING SETTINGS
# ============================================================================

MESSAGE_SEND_DELAY = 0.5
"""Delay between sending messages (in seconds) to avoid rate limiting."""

OUTBOX_MAX_AGE_HOURS = 24
"""Pending notifications older than this are expired instead of being retried."""

OUTBOX_MAX_ATTEMPTS = 5
"""Pending notifications that have been attempted this many times are expired."""

# ============================================================================
# SCRAPER SETTINGS
# ============================================================================

MAX_RETRY_ATTEMPTS = 3
"""Maximum number of retry attempts for scraping operations."""

RETRY_BACKOFF_FACTOR = 2
"""Multiplier for exponential backoff in retries."""

SCRAPING_FAILURE_GRACE_PERIOD = 2
"""Number of consecutive misses before declaring an item as genuinely delisted."""

STOCKIST_FAILURE_ALERT_THRESHOLD = 6
"""Consecutive failed runs before a "stockist keeps failing" message is sent
   (about an hour at the documented 10-minute schedule)."""

STOCKIST_HEALTH_RATIO = 0.5
"""If current scraped item count is less than this ratio of the previous count,
   the stockist is considered unhealthy and delisting is skipped for that run."""

CONSECUTIVE_UNHEALTHY_THRESHOLD = 2
"""Number of consecutive unhealthy observations (low ratio) required before
   accepting a lowered item count as the new healthy baseline."""

NOTIFICATION_COOLDOWN_MINUTES = 60
"""Minimum minutes between sending the same notification for an item with the same status."""

# ============================================================================
# DATABASE SETTINGS
# ============================================================================

DB_POOL_SIZE = 10
"""Connection pool size for database."""

DB_MAX_OVERFLOW = 20
"""Maximum overflow connections for database."""

# ============================================================================
# USER AGENT SETTINGS
# ============================================================================

FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
]
"""Fallback user agents if online fetch fails."""
