import logging
import re
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as db
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config.config import Database as Database_
from constants import (
    DB_MAX_OVERFLOW,
    DB_POOL_SIZE,
    NOTIFICATION_COOLDOWN_MINUTES,
    SCRAPING_FAILURE_GRACE_PERIOD,
)
from stockist.stockist import Stock

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class AmiiboStock(Base):
    __tablename__ = "amiibo_stock"
    __table_args__ = (UniqueConstraint("Website", "URL"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    Website: Mapped[str]
    Title: Mapped[str]
    Price: Mapped[str]
    Stock: Mapped[str]
    Colour: Mapped[str]
    URL: Mapped[str]
    Image: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(default=datetime.now)
    missed_count: Mapped[int] = mapped_column(default=0)
    last_notified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_notified_status: Mapped[str | None] = mapped_column(nullable=True)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    website: Mapped[str]
    url: Mapped[str]
    title: Mapped[str]
    stock_status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class LastScraped(Base):
    __tablename__ = "last_scraped"

    stockist: Mapped[str] = mapped_column(primary_key=True)
    last_attempt_at: Mapped[datetime] = mapped_column(default=datetime.now)
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_healthy_count: Mapped[int] = mapped_column(default=0)
    consecutive_unhealthy_obs: Mapped[int] = mapped_column(default=0)


class ScrapingFailure(Base):
    """Track scraping failures to prevent false notifications."""

    __tablename__ = "scraping_failures"

    stockist: Mapped[str] = mapped_column(primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    last_failure: Mapped[datetime] = mapped_column(default=datetime.now)
    last_success: Mapped[datetime | None] = mapped_column(nullable=True)


class Database:
    def __init__(self, config: Database_) -> None:
        pool_kwargs: dict[str, Any] = dict(
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_pre_ping=True,
        )
        if config.engine == "postgres":
            url = db.URL.create(
                "postgresql+psycopg2",
                username=config.username,
                password=config.password,
                host=str(config.host) if config.host else "127.0.0.1",
                port=config.port or 5432,
                database=config.name,
            )
            self.engine = db.create_engine(url, **pool_kwargs)
        elif config.engine == "sqlite":
            self.engine = db.create_engine(
                "sqlite:///" + config.name + ".db?check_same_thread=false"
            )
        else:
            raise ValueError(f"{config.engine} engine is not supported")

        log.info(f"{config.engine} engine created")

        self._engine_type = config.engine
        self.Session = sessionmaker(bind=self.engine)

    def ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self._run_migrations()
        log.info("database schema ensured")

    def _run_migrations(self) -> None:
        if self._engine_type == "sqlite":
            with self.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(amiibo_stock)"))
                amiibo_cols = [row[1] for row in result]
                if "missed_count" not in amiibo_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE amiibo_stock ADD COLUMN missed_count INTEGER DEFAULT 0"
                        )
                    )
                if "last_notified_at" not in amiibo_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE amiibo_stock ADD COLUMN last_notified_at TIMESTAMP"
                        )
                    )
                if "last_notified_status" not in amiibo_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE amiibo_stock ADD COLUMN last_notified_status VARCHAR"
                        )
                    )
                result = conn.execute(db.text("PRAGMA table_info(last_scraped)"))
                scraped_cols = [row[1] for row in result]
                if "last_attempt_at" not in scraped_cols:
                    if "timestamp" in scraped_cols:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped RENAME COLUMN timestamp TO last_attempt_at"
                            )
                        )
                    else:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped ADD COLUMN last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                            )
                        )
                if "last_healthy_count" not in scraped_cols:
                    if "item_count" in scraped_cols:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped RENAME COLUMN item_count TO last_healthy_count"
                            )
                        )
                    else:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped ADD COLUMN last_healthy_count INTEGER DEFAULT 0"
                            )
                        )
                if "last_success_at" not in scraped_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE last_scraped ADD COLUMN last_success_at TIMESTAMP"
                        )
                    )
                if "consecutive_unhealthy_obs" not in scraped_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE last_scraped ADD COLUMN consecutive_unhealthy_obs INTEGER DEFAULT 0"
                        )
                    )
                conn.commit()
        elif self._engine_type == "postgres":
            with self.engine.connect() as conn:
                result = conn.execute(
                    db.text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name = 'amiibo_stock'"
                    )
                )
                amiibo_cols = [row[0] for row in result]
                if "missed_count" not in amiibo_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE amiibo_stock ADD COLUMN missed_count INTEGER DEFAULT 0"
                        )
                    )
                if "last_notified_at" not in amiibo_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE amiibo_stock ADD COLUMN last_notified_at TIMESTAMP"
                        )
                    )
                if "last_notified_status" not in amiibo_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE amiibo_stock ADD COLUMN last_notified_status VARCHAR"
                        )
                    )
                result = conn.execute(
                    db.text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name = 'last_scraped'"
                    )
                )
                scraped_cols = [row[0] for row in result]
                if "last_attempt_at" not in scraped_cols:
                    if "timestamp" in scraped_cols:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped RENAME COLUMN timestamp TO last_attempt_at"
                            )
                        )
                    else:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped ADD COLUMN last_attempt_at TIMESTAMP DEFAULT NOW()"
                            )
                        )
                if "last_healthy_count" not in scraped_cols:
                    if "item_count" in scraped_cols:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped RENAME COLUMN item_count TO last_healthy_count"
                            )
                        )
                    else:
                        conn.execute(
                            db.text(
                                "ALTER TABLE last_scraped ADD COLUMN last_healthy_count INTEGER DEFAULT 0"
                            )
                        )
                if "last_success_at" not in scraped_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE last_scraped ADD COLUMN last_success_at TIMESTAMP"
                        )
                    )
                if "consecutive_unhealthy_obs" not in scraped_cols:
                    conn.execute(
                        db.text(
                            "ALTER TABLE last_scraped ADD COLUMN consecutive_unhealthy_obs INTEGER DEFAULT 0"
                        )
                    )
                conn.commit()

    def remove_currency(self, currency_string: str) -> float:
        """Extract numeric price from currency string.

        Handles various formats:
        - $19.99 -> 19.99
        - £1,234.56 -> 1234.56
        - €1.234,56 -> 1234.56 (EU format)
        - €12.34 -> 12.34

        Args:
            currency_string: String containing currency and price

        Returns:
            Float value of the price

        Raises:
            ValueError: If no valid number can be extracted
        """
        # Remove common currency symbols and whitespace
        cleaned = (
            currency_string.replace("$", "")
            .replace("£", "")
            .replace("€", "")
            .replace("¥", "")
            .strip()
        )

        # Handle cases with both comma and period
        if "," in cleaned and "." in cleaned:
            last_comma_idx = cleaned.rfind(",")
            last_period_idx = cleaned.rfind(".")

            if last_comma_idx > last_period_idx:
                # EU format: "1.234,56" - period is thousands, comma is decimal
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # US/UK format: "1,234.56" - comma is thousands, period is decimal
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Only comma, treat as decimal separator (EU format)
            cleaned = cleaned.replace(",", ".")
        # If only period, leave as is (already correct)

        # Extract all digits and decimal point

        match = re.search(r"[\d.]+", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass

        # Fallback: remove all non-digits except decimal point
        trim = re.compile(r"[^\d.]+")
        cleaned = trim.sub("", cleaned)
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Could not extract price from: {currency_string}")

    def record_scrape_attempt(
        self, stockist: str, item_count: int | None = None
    ) -> None:
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                session.add(
                    LastScraped(
                        stockist=stockist,
                        last_attempt_at=datetime.now(),
                        last_healthy_count=(
                            item_count if item_count is not None else 0
                        ),
                    )
                )
            else:
                existing.last_attempt_at = datetime.now()
            session.commit()

    def record_healthy_scrape(self, stockist: str, item_count: int) -> None:
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                session.add(
                    LastScraped(
                        stockist=stockist,
                        last_attempt_at=datetime.now(),
                        last_success_at=datetime.now(),
                        last_healthy_count=item_count,
                        consecutive_unhealthy_obs=0,
                    )
                )
            else:
                existing.last_success_at = datetime.now()
                existing.last_healthy_count = item_count
                existing.consecutive_unhealthy_obs = 0
            session.commit()

    def record_unhealthy_scrape(self, stockist: str) -> int:
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                existing = LastScraped(
                    stockist=stockist,
                    last_attempt_at=datetime.now(),
                    consecutive_unhealthy_obs=1,
                )
                session.add(existing)
            else:
                existing.consecutive_unhealthy_obs += 1
            session.commit()
            return existing.consecutive_unhealthy_obs

    def get_consecutive_unhealthy_obs(self, stockist: str) -> int:
        with self.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            if record is None:
                return 0
            return record.consecutive_unhealthy_obs

    def record_scraping_failure(self, stockist: str) -> int:
        """Record a scraping failure and return consecutive failure count.

        Args:
            stockist: Name of the stockist that failed

        Returns:
            Number of consecutive failures
        """
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is None:
                failure = ScrapingFailure(
                    stockist=stockist,
                    consecutive_failures=1,
                    last_failure=datetime.now(),
                    last_success=None,
                )
                session.add(failure)
            else:
                failure.consecutive_failures += 1
                failure.last_failure = datetime.now()

            session.commit()
            count = failure.consecutive_failures

        log.warning(f"{stockist} has {count} consecutive scraping failure(s)")
        return count

    def record_scraping_success(self, stockist: str) -> None:
        """Record a successful scrape, resetting failure count.

        Args:
            stockist: Name of the stockist that succeeded
        """
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is not None:
                if failure.consecutive_failures > 0:
                    log.info(
                        f"{stockist} scraping recovered after {failure.consecutive_failures} failure(s)"
                    )
                failure.consecutive_failures = 0
                failure.last_success = datetime.now()
                session.commit()

    def get_consecutive_failures(self, stockist: str) -> int:
        """Get the number of consecutive failures for a stockist.

        Args:
            stockist: Name of the stockist

        Returns:
            Number of consecutive failures (0 if none)
        """
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is None:
                return 0
            return failure.consecutive_failures

    def get_last_healthy_count(self, stockist: str) -> int:
        with self.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            if record is None:
                return 0
            return record.last_healthy_count

    def should_suppress_notification(self, url: str, website: str, stock: str) -> bool:
        """Check if a notification should be suppressed due to cooldown.

        Args:
            url: Product URL
            website: Website name
            stock: Current stock status string

        Returns:
            True if notification should be suppressed
        """
        with self.Session() as session:
            item = (
                session.query(AmiiboStock).filter_by(URL=url, Website=website).first()
            )
            if item and item.last_notified_at:
                cooldown_end = item.last_notified_at + timedelta(
                    minutes=NOTIFICATION_COOLDOWN_MINUTES
                )
                if datetime.now() < cooldown_end and item.last_notified_status == stock:
                    return True
        return False

    def record_notification(self, url: str, website: str, stock: str) -> None:
        """Record that a notification was sent for an item.

        Args:
            url: Product URL
            website: Website name
            stock: Stock status that was notified
        """
        with self.Session() as session:
            item = (
                session.query(AmiiboStock).filter_by(URL=url, Website=website).first()
            )
            if item:
                item.last_notified_at = datetime.now()
                item.last_notified_status = stock
                session.commit()

    def _get_existing_items(self, website: str) -> list[AmiiboStock]:
        """Retrieve all existing items for a website."""
        with self.Session() as session:
            return session.query(AmiiboStock).filter_by(Website=website).all()

    def _handle_price_change(
        self, session: Any, item: AmiiboStock, new_price: str
    ) -> dict[str, Any]:
        log.info(f"Price changed for {item.Title} from {item.Price} to {new_price}")
        item.Price = new_price
        return {
            "Colour": 0xFFFFFF,
            "Title": item.Title,
            "Image": item.Image,
            "URL": item.URL,
            "Price": new_price,
            "Stock": Stock.PRICE_CHANGE.value,
            "Website": item.Website,
        }

    def _handle_delisted_item(self, session: Any, item: AmiiboStock) -> dict[str, Any]:
        log.info(f"{item.Title} is no longer listed")
        session.delete(item)
        return {
            "Colour": 0xFF0000,
            "Title": item.Title,
            "Image": item.Image,
            "URL": item.URL,
            "Price": item.Price,
            "Stock": Stock.DELISTED.value,
            "Website": item.Website,
        }

    def _add_new_items(
        self, session: Any, new_items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        added = []
        for datum in new_items:
            log.info(f"Adding {datum['Title']}")
            amiibo = AmiiboStock(
                Website=datum["Website"],
                Title=datum["Title"],
                Price=datum["Price"],
                Stock=datum["Stock"],
                Colour=datum["Colour"],
                URL=datum["URL"],
                Image=datum["Image"],
                timestamp=datetime.now(),
            )
            session.add(amiibo)
            added.append(datum)
        return added

    def check_then_add_or_update_amiibo(
        self, data: list[dict[str, Any]], skip_delisting: bool = False
    ) -> list[dict[str, Any]]:
        if not data:
            return []

        statistics = {"New": 0, "Updated": 0, "Deleted": 0}
        output: list[dict[str, Any]] = []
        website = data[0]["Website"]

        with self.Session() as session:
            try:
                existing_items = (
                    session.query(AmiiboStock).filter_by(Website=website).all()
                )

                if not existing_items:
                    added = self._add_new_items(session, data)
                    statistics["New"] = len(added)
                    log.info(f"New items saved: {statistics['New']}")
                    session.commit()
                    return added

                existing_map = {
                    item.URL: (item.id, item.Price, item.Title, item.Image)
                    for item in existing_items
                }
                new_data_map = {datum["URL"]: datum for datum in data}

                for item in existing_items:
                    if item.URL in new_data_map:
                        new_datum = new_data_map[item.URL]
                        item.missed_count = 0
                        if self.remove_currency(
                            new_datum["Price"]
                        ) != self.remove_currency(item.Price):
                            statistics["Updated"] += 1
                            output.append(
                                self._handle_price_change(
                                    session, item, new_datum["Price"]
                                )
                            )
                    elif skip_delisting:
                        log.debug(
                            f"Skipping delisting check for {item.Title} (health check active)"
                        )
                    else:
                        item.missed_count += 1
                        log.info(
                            f"{item.Title} missed {item.missed_count} time(s) "
                            f"(grace: {SCRAPING_FAILURE_GRACE_PERIOD})"
                        )
                        if item.missed_count >= SCRAPING_FAILURE_GRACE_PERIOD:
                            statistics["Deleted"] += 1
                            output.append(self._handle_delisted_item(session, item))

                new_items = [d for d in data if d["URL"] not in existing_map]
                if new_items:
                    added = self._add_new_items(session, new_items)
                    output.extend(added)
                    statistics["New"] = len(added)

                session.commit()
            except Exception:
                session.rollback()
                raise

        log.info(
            f"Added: {statistics['New']}, "
            f"Updated: {statistics['Updated']}, "
            f"Deleted: {statistics['Deleted']}"
        )
        return output

    def get_statistics(self) -> dict[str, int]:
        """Get database statistics.

        Returns:
            Dictionary with counts of total items, stockists, etc.
        """
        with self.Session() as session:
            total_items = session.query(AmiiboStock).count()
            total_stockists = session.query(LastScraped).count()

            stats = {
                "total_amiibo": total_items,
                "total_stockists": total_stockists,
            }

            log.debug(f"Database statistics: {stats}")
            return stats

    def cleanup_old_records(self, days_old: int = 30) -> int:
        """Remove old scraped records older than specified days.

        Args:
            days_old: Number of days to keep records

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)

        with self.Session() as session:
            deleted = (
                session.query(AmiiboStock)
                .filter(AmiiboStock.timestamp < cutoff_date)
                .delete()
            )
            session.commit()

            if deleted > 0:
                log.info(
                    f"Cleaned up {deleted} old records (older than {days_old} days)"
                )

            return deleted

    @staticmethod
    def _validate_amiibo_data(data: dict[str, Any]) -> bool:
        """Validate that amiibo data has all required fields.

        Required fields:
        - Title: str - Product title
        - Price: str - Price string
        - Stock: str - Stock status
        - URL: str - Product URL
        - Website: str - Website name
        - Image: str - Image URL
        - Colour: int - Discord color code

        Args:
            data: Dictionary containing amiibo data

        Returns:
            True if data is valid

        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = {
            "Title": (str, "Product title"),
            "Price": (str, "Price string"),
            "Stock": (str, "Stock status"),
            "URL": (str, "Product URL"),
            "Website": (str, "Website name"),
            "Image": (str, "Image URL"),
            "Colour": (int, "Discord color code"),
        }

        missing_fields = []
        invalid_fields = []

        for field, (expected_type, description) in required_fields.items():
            if field not in data:
                missing_fields.append(f"{field} ({description})")
            elif not isinstance(data[field], expected_type):
                invalid_fields.append(
                    f"{field}: expected {expected_type.__name__}, got {type(data[field]).__name__}"
                )
            elif isinstance(data[field], str) and not data[field].strip():
                invalid_fields.append(f"{field}: empty string not allowed")

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        if invalid_fields:
            raise ValueError(f"Invalid field types: {', '.join(invalid_fields)}")

        return True
