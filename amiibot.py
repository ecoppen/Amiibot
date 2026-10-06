import argparse
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
from utils import JSONFormatter

logs_file = Path(Path().resolve(), LOG_FILE_NAME)

log = logging.getLogger(__name__)

_HUMAN_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_HUMAN_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_json: bool = False) -> None:
    """Configure rotating file and console handlers.

    File logs are always JSON lines. Console output is human-readable by
    default; pass ``log_json=True`` to emit JSON on the console too.
    """
    file_formatter: logging.Formatter = JSONFormatter()
    console_formatter: logging.Formatter = (
        JSONFormatter()
        if log_json
        else logging.Formatter(_HUMAN_FORMAT, datefmt=_HUMAN_DATEFMT)
    )

    rotating_handler = RotatingFileHandler(
        logs_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    rotating_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    logging.basicConfig(
        level=os.environ.get("LOGLEVEL", "INFO"),
        handlers=[rotating_handler, console_handler],
        force=True,
    )

    for handler in logging.getLogger().handlers:
        handler.addFilter(SecretRedactionFilter())


class SecretRedactionFilter(logging.Filter):
    """Redact secrets from everything a record can render.

    The message is fully rendered first, so secrets inside non-string
    arguments (for example an exception whose text contains a webhook URL)
    are caught. Tracebacks and string-valued ``extra`` fields are redacted too.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = f"{record.msg} {record.args}"
        record.msg = redact_secrets(message)
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact_secrets(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_secrets(record.stack_info)
        for key, value in list(record.__dict__.items()):
            if key not in JSONFormatter.SKIPPED_KEYS and isinstance(value, str):
                record.__dict__[key] = redact_secrets(value)
        return True


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


def main(log_json: bool = False) -> RunResult:
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
    parser = argparse.ArgumentParser(description="Amiibo stock checker and notifier")
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Emit JSON log lines on the console (file logs are always JSON)",
    )
    args = parser.parse_args()
    setup_logging(log_json=args.log_json)
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
