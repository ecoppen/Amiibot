import logging
import os
import signal
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config.config import load_config
from constants import LOG_FILE_NAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT
from database import Database
from messenger.manager import MessageManager
from scraper import Scraper
from stockist.manager import StockistManager

# Setup logging with rotation
logs_file = Path(Path().resolve(), LOG_FILE_NAME)
logs_file.touch(exist_ok=True)

# Create logger
log = logging.getLogger(__name__)

# Setup rotating file handler
rotating_handler = RotatingFileHandler(
    logs_file,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
)
rotating_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

# Setup console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    handlers=[rotating_handler, console_handler],
)

log = logging.getLogger(__name__)

# Global references for cleanup
_database: Database | None = None
_messengers: MessageManager | None = None


def cleanup(signum: int | None = None, frame: object | None = None) -> None:
    """Gracefully shutdown and cleanup resources.

    Args:
        signum: Signal number (for signal handlers)
        frame: Stack frame (for signal handlers)
    """
    log.info("Shutting down gracefully...")
    if _database is not None:
        try:
            log.info("Closing database connection...")
            _database.Session().close()
        except Exception as e:
            log.warning(f"Error closing database: {e}")
    log.info("Shutdown complete")
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

try:
    config_path = Path("config", "config.json")
    config = load_config(path=config_path)
    log.info(f"{config_path} loaded")

    _database = Database(config=config.database)
    _messengers = MessageManager(config=config.messengers)
    stockists = StockistManager(messengers=_messengers)
    scraper = Scraper(config=config, stockists=stockists, database=_database)

    log.info("Starting scraper...")
    scraper.scrape()
    log.info("Scraper completed successfully")

except KeyboardInterrupt:
    log.info("Interrupted by user")
    cleanup()
except Exception as e:
    log.error(f"Fatal error: {e}", exc_info=True)
    cleanup()
    sys.exit(1)
