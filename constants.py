"""
Application constants for Amiibot.

Centralized configuration for magic numbers, timeouts, colors, and other constants.
"""

# ============================================================================
# TIMEOUT SETTINGS (in seconds)
# ============================================================================

REQUEST_TIMEOUT = 5
"""Default timeout for HTTP requests."""

SELENIUM_WAIT_TIME = 5
"""Time to wait for JavaScript rendering in Selenium."""

SELENIUM_WAIT_MAX = 20
"""Maximum wait time for Selenium WebDriver operations."""

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

# ============================================================================
# STOCK STATUS COLORS (Discord embed colors)
# ============================================================================

COLOR_IN_STOCK = 0x00FF00
"""Color for 'In Stock' status (green)."""

COLOR_OUT_OF_STOCK = 0xFF0000
"""Color for 'Out of Stock' status (red)."""

COLOR_PRICE_CHANGE = 0xFFFFFF
"""Color for 'Price Change' status (white)."""

COLOR_DELISTED = 0xFF0000
"""Color for 'Delisted' status (red)."""

COLOR_DEFAULT = 0x0000FF
"""Default color for other statuses (blue)."""

# ============================================================================
# SCRAPER SETTINGS
# ============================================================================

MAX_RETRY_ATTEMPTS = 3
"""Maximum number of retry attempts for scraping operations."""

RETRY_BACKOFF_FACTOR = 2
"""Multiplier for exponential backoff in retries."""

MIN_ITEMS_THRESHOLD = 1
"""Minimum number of items expected from scraper. If 0 items returned,
   assume scraping failure and skip database update to prevent false notifications."""

SCRAPING_FAILURE_GRACE_PERIOD = 2
"""Number of consecutive empty scrapes before treating as real delisting (not implemented yet)."""

# ============================================================================
# DATABASE SETTINGS
# ============================================================================

DB_POOL_SIZE = 10
"""Connection pool size for database."""

DB_MAX_OVERFLOW = 20
"""Maximum overflow connections for database."""

# ============================================================================
# PARSING SETTINGS
# ============================================================================

MAX_PRICE_DECIMALS = 2
"""Maximum decimal places for price parsing."""

# ============================================================================
# USER AGENT SETTINGS
# ============================================================================

FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
]
"""Fallback user agents if online fetch fails."""
