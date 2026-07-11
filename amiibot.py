import fcntl
import io
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config.config import load_config, redact_secrets
from constants import LOG_FILE_NAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT
from database import Database
from messenger.manager import MessageManager
from result import FailureCategory, RunResult, RunStatus
from scraper import Scraper
from stockist.manager import StockistManager

logs_file = Path(Path().resolve(), LOG_FILE_NAME)
logs_file.touch(exist_ok=True)

log = logging.getLogger(__name__)

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


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args and isinstance(record.args, tuple):
            record.args = tuple(
                redact_secrets(str(a)) if isinstance(a, str) else a for a in record.args
            )
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(SecretRedactionFilter())

log = logging.getLogger(__name__)

_database: Database | None = None
_messengers: MessageManager | None = None
_lock_file: io.TextIOWrapper | None = None
_LOCK_PATH = Path(Path().resolve(), ".amiibot.lock")


def cleanup() -> None:
    """Release resources without deciding the process exit code."""
    log.info("Shutting down gracefully...")
    global _lock_file
    if _lock_file is not None:
        try:
            fcntl.flock(_lock_file, fcntl.LOCK_UN)
            _lock_file.close()
        except Exception as e:
            log.warning(f"Error releasing lock: {e}")
        _lock_file = None
        try:
            _LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
    if _database is not None:
        try:
            log.info("Disposing database engine...")
            _database.engine.dispose()
        except Exception as e:
            log.warning(f"Error disposing database: {e}")
    log.info("Shutdown complete")


def main() -> RunResult:
    global _lock_file
    try:
        _lock_file = open(_LOCK_PATH, "w")
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        log.error("Another instance is already running. Exiting.")
        return RunResult(
            status=RunStatus.FAILURE,
            exit_code=1,
            failure_category=FailureCategory.UNEXPECTED,
            errors=["Another instance is already running"],
        )

    config_path = Path("config", "config.json")
    config = load_config(path=config_path)
    log.info(f"{config_path} loaded")

    global _database, _messengers
    _database = Database(config=config.database)
    _database.ensure_schema()
    _messengers = MessageManager(config=config.messengers)
    stockists = StockistManager(messengers=_messengers)
    scraper = Scraper(config=config, stockists=stockists, database=_database)

    log.info("Starting scraper...")
    result = scraper.scrape()
    log.info(f"Scraper completed: {result.status.name}")
    return result


if __name__ == "__main__":
    try:
        result = main()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        result = RunResult(
            status=RunStatus.FAILURE,
            exit_code=130,
            failure_category=FailureCategory.UNEXPECTED,
            errors=["Interrupted by user"],
        )
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        result = RunResult(
            status=RunStatus.FAILURE,
            exit_code=1,
            failure_category=FailureCategory.UNEXPECTED,
            errors=[str(e)],
        )
    finally:
        cleanup()
        log.info(
            f"Run summary: status={result.status.name} "
            f"exit={result.exit_code} "
            f"stockists={result.stockists_succeeded}/{result.stockists_attempted} "
            f"notifications={result.notifications_sent}"
        )
        if result.errors:
            for err in result.errors[:5]:
                log.info(f"  error: {err}")
    raise SystemExit(result.exit_code)
