import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import sqlalchemy as db
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from config.config import DatabaseConfig as Database_
from constants import (
    DB_MAX_OVERFLOW,
    DB_POOL_SIZE,
    FLAP_ALERT_COOLDOWN_MINUTES,
    FLAP_TRANSITION_THRESHOLD,
    FLAP_WINDOW_MINUTES,
    NOTIFICATION_COOLDOWN_MINUTES,
    SCRAPING_FAILURE_GRACE_PERIOD,
)
from stockist.stockist import URGENT_STATUSES, Stock
from timeutil import utcnow

log = logging.getLogger(__name__)

OUTBOX_PENDING = "pending"
OUTBOX_DONE = "done"
OUTBOX_EXPIRED = "expired"

# Dialect-specific fragments used in the migration DDL below. A "{name}"
# placeholder in a DDL string is replaced with the entry for the engine in use.
_DIALECT_DDL: dict[str, dict[str, str]] = {
    "sqlite": {"true": "1", "now_utc": "CURRENT_TIMESTAMP"},
    "postgres": {"true": "true", "now_utc": "(NOW() AT TIME ZONE 'UTC')"},
}

# Columns added to existing tables after their original creation, as
# (table, column, DDL type and default). Applied in order, only when missing.
_MIGRATION_ADDITIONS: list[tuple[str, str, str]] = [
    ("amiibo_stock", "missed_count", "INTEGER DEFAULT 0"),
    ("amiibo_stock", "last_notified_at", "TIMESTAMP"),
    ("amiibo_stock", "last_notified_status", "VARCHAR"),
    ("amiibo_stock", "is_active", "BOOLEAN DEFAULT {true}"),
    ("amiibo_stock", "delisted_at", "TIMESTAMP"),
    ("amiibo_stock", "first_seen_at", "TIMESTAMP"),
    ("amiibo_stock", "flap_count", "INTEGER DEFAULT 0"),
    ("amiibo_stock", "last_flap_at", "TIMESTAMP"),
    ("last_scraped", "last_attempt_at", "TIMESTAMP DEFAULT {now_utc}"),
    ("last_scraped", "last_healthy_count", "INTEGER DEFAULT 0"),
    ("last_scraped", "last_success_at", "TIMESTAMP"),
    ("last_scraped", "consecutive_unhealthy_obs", "INTEGER DEFAULT 0"),
    ("notification_outbox", "price", "VARCHAR DEFAULT ''"),
    ("notification_outbox", "image", "VARCHAR DEFAULT ''"),
    ("notification_outbox", "colour", "INTEGER DEFAULT 0"),
    ("notification_outbox", "status", "VARCHAR DEFAULT 'pending'"),
    ("notification_outbox", "attempts", "INTEGER DEFAULT 0"),
    ("notification_outbox", "last_attempt_at", "TIMESTAMP"),
    ("notification_outbox", "completed_at", "TIMESTAMP"),
    ("notification_outbox", "release_date", "VARCHAR"),
    ("scraping_failures", "alert_sent_at", "TIMESTAMP"),
]

# Columns renamed after the table was first created, as (table, old, new).
# Applied before the additions, and only when the old column exists and the new
# one does not, so the data in the old column is kept.
_MIGRATION_RENAMES: list[tuple[str, str, str]] = [
    ("last_scraped", "timestamp", "last_attempt_at"),
    ("last_scraped", "item_count", "last_healthy_count"),
]


class UTCDateTime(TypeDecorator[datetime]):
    """A datetime column that is aware UTC in Python and naive UTC in the database.

    Neither sqlite nor Postgres ``TIMESTAMP`` (without time zone) keeps a zone,
    so values are stored as naive UTC and tagged as UTC again on the way out.

    Writing: aware values are converted to UTC and stripped of their tzinfo.
    Naive values are rejected with ``ValueError``: guessing a zone is how
    local-time bugs creep back in, so callers must pass aware datetimes
    (use ``timeutil.utcnow()``).

    Reading: stored values are returned as aware UTC.

    NOTE: rows written before this type existed hold naive *local* times. They
    are now read as UTC, a one-off shift of at most an hour (the UK offset
    from UTC). No data migration is done; cooldowns and outbox ages simply
    start counting from slightly different instants.
    """

    impl = db.DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "naive datetime passed to a UTCDateTime column; use an aware datetime"
            )
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: UTCDateTime}


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
    timestamp: Mapped[datetime] = mapped_column(default=utcnow)
    missed_count: Mapped[int] = mapped_column(default=0)
    last_notified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_notified_status: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    delisted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    flap_count: Mapped[int] = mapped_column(default=0)
    last_flap_at: Mapped[datetime | None] = mapped_column(nullable=True)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    website: Mapped[str]
    url: Mapped[str]
    title: Mapped[str]
    stock_status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    price: Mapped[str] = mapped_column(default="")
    image: Mapped[str] = mapped_column(default="")
    colour: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default=OUTBOX_PENDING)
    attempts: Mapped[int] = mapped_column(default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    release_date: Mapped[str | None] = mapped_column(nullable=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("idempotency_key", "messenger_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str]
    website: Mapped[str]
    url: Mapped[str]
    title: Mapped[str]
    stock_status: Mapped[str]
    messenger_name: Mapped[str]
    delivery_status: Mapped[str]
    delivered_at: Mapped[datetime] = mapped_column(default=utcnow)


class LastScraped(Base):
    __tablename__ = "last_scraped"

    stockist: Mapped[str] = mapped_column(primary_key=True)
    last_attempt_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_healthy_count: Mapped[int] = mapped_column(default=0)
    consecutive_unhealthy_obs: Mapped[int] = mapped_column(default=0)


class ScrapingFailure(Base):
    """Track scraping failures to prevent false notifications."""

    __tablename__ = "scraping_failures"

    stockist: Mapped[str] = mapped_column(primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    last_failure: Mapped[datetime] = mapped_column(default=utcnow)
    last_success: Mapped[datetime | None] = mapped_column(nullable=True)
    alert_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)


@dataclass(frozen=True)
class ScrapingRecovery:
    """What a successful scrape replaced: the failure streak and its alert."""

    previous_failures: int = 0
    alert_sent: bool = False


class Database:
    def __init__(self, config: Database_) -> None:
        pool_kwargs: dict[str, Any] = {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_pre_ping": True,
        }
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
        """Bring tables created by older versions up to the current schema.

        Idempotent. Tables that do not exist are skipped. Existing columns are
        read with the SQLAlchemy inspector, so this works the same on sqlite
        and Postgres; only the DDL fragments differ (see _DIALECT_DDL).
        """
        fragments = _DIALECT_DDL[self._engine_type]
        tables = dict.fromkeys(t for t, _, _ in _MIGRATION_ADDITIONS)
        with self.engine.begin() as conn:
            inspector = db.inspect(conn)
            for table in tables:
                if not inspector.has_table(table):
                    continue
                existing = {col["name"] for col in inspector.get_columns(table)}
                for tbl, old, new in _MIGRATION_RENAMES:
                    if tbl == table and old in existing and new not in existing:
                        conn.execute(
                            db.text(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")
                        )
                        existing.discard(old)
                        existing.add(new)
                for tbl, column, ddl in _MIGRATION_ADDITIONS:
                    if tbl != table:
                        continue
                    if column not in existing:
                        conn.execute(
                            db.text(
                                f"ALTER TABLE {table} ADD COLUMN {column} "
                                + ddl.format(**fragments)
                            )
                        )
                        existing.add(column)

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

    def _prices_differ(self, old: str, new: str) -> bool:
        """Return True if two price strings represent different prices.

        Compares numerically when both parse, so formatting-only changes (extra
        whitespace, currency symbols) are ignored. If either cannot be parsed
        (e.g. "Price TBC"), falls back to comparing the whitespace-normalised
        strings, so one odd price never aborts the whole update.
        """
        try:
            return self.remove_currency(old) != self.remove_currency(new)
        except ValueError:
            log.debug(f"Could not parse price(s) {old!r} / {new!r}; comparing as text")
            return " ".join(str(old).split()) != " ".join(str(new).split())

    def record_scrape_attempt(self, stockist: str) -> None:
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                session.add(
                    LastScraped(
                        stockist=stockist,
                        last_attempt_at=utcnow(),
                        last_healthy_count=0,
                    )
                )
            else:
                existing.last_attempt_at = utcnow()
            session.commit()

    def record_healthy_scrape(self, stockist: str, item_count: int) -> None:
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                session.add(
                    LastScraped(
                        stockist=stockist,
                        last_attempt_at=utcnow(),
                        last_success_at=utcnow(),
                        last_healthy_count=item_count,
                        consecutive_unhealthy_obs=0,
                    )
                )
            else:
                existing.last_success_at = utcnow()
                existing.last_healthy_count = item_count
                existing.consecutive_unhealthy_obs = 0
            session.commit()

    def record_unhealthy_scrape(self, stockist: str) -> int:
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                existing = LastScraped(
                    stockist=stockist,
                    last_attempt_at=utcnow(),
                    consecutive_unhealthy_obs=1,
                )
                session.add(existing)
            else:
                existing.consecutive_unhealthy_obs += 1
            session.commit()
            return existing.consecutive_unhealthy_obs

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
                    last_failure=utcnow(),
                    last_success=None,
                )
                session.add(failure)
            else:
                failure.consecutive_failures += 1
                failure.last_failure = utcnow()

            session.commit()
            count = failure.consecutive_failures

        log.warning(f"{stockist} has {count} consecutive scraping failure(s)")
        return count

    def record_scraping_success(self, stockist: str) -> ScrapingRecovery:
        """Record a successful scrape, resetting failure count.

        The failure alert flag is left alone so the caller can send a recovery
        message and then call clear_failure_alert.

        Args:
            stockist: Name of the stockist that succeeded

        Returns:
            The failure streak that was just reset and whether it had been alerted
        """
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is None:
                return ScrapingRecovery()
            recovery = ScrapingRecovery(
                previous_failures=failure.consecutive_failures,
                alert_sent=failure.alert_sent_at is not None,
            )
            if failure.consecutive_failures > 0:
                log.info(
                    f"{stockist} scraping recovered after {failure.consecutive_failures} failure(s)"
                )
            failure.consecutive_failures = 0
            failure.last_success = utcnow()
            session.commit()
            return recovery

    def get_failure_alert_state(self, stockist: str) -> tuple[int, datetime | None]:
        """Return (consecutive failures, when the failure alert was sent or None)."""
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is None:
                return 0, None
            return failure.consecutive_failures, failure.alert_sent_at

    def mark_failure_alert_sent(self, stockist: str) -> None:
        """Remember that the "stockist keeps failing" alert has been delivered."""
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is not None:
                failure.alert_sent_at = utcnow()
                session.commit()

    def clear_failure_alert(self, stockist: str) -> None:
        """Forget the failure alert so a future failure streak can alert again."""
        with self.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            if failure is not None and failure.alert_sent_at is not None:
                failure.alert_sent_at = None
                session.commit()

    def get_last_healthy_count(self, stockist: str) -> int:
        with self.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            if record is None:
                return 0
            return record.last_healthy_count

    def record_delivery(
        self,
        idempotency_key: str,
        website: str,
        url: str,
        title: str,
        stock_status: str,
        messenger_name: str,
        delivery_status: str,
    ) -> None:
        with self.Session() as session:
            existing = (
                session.query(NotificationDelivery)
                .filter_by(
                    idempotency_key=idempotency_key,
                    messenger_name=messenger_name,
                )
                .first()
            )
            if existing is not None:
                existing.delivery_status = delivery_status
                existing.delivered_at = utcnow()
                session.commit()
                return
            delivery = NotificationDelivery(
                idempotency_key=idempotency_key,
                website=website,
                url=url,
                title=title,
                stock_status=stock_status,
                messenger_name=messenger_name,
                delivery_status=delivery_status,
            )
            session.add(delivery)
            session.commit()

    def get_delivery_status(
        self, idempotency_key: str, messenger_name: str
    ) -> str | None:
        """Return the recorded delivery status for (key, messenger), if any."""
        with self.Session() as session:
            delivery = (
                session.query(NotificationDelivery)
                .filter_by(
                    idempotency_key=idempotency_key,
                    messenger_name=messenger_name,
                )
                .first()
            )
            return delivery.delivery_status if delivery is not None else None

    def get_pending_outbox(self, website: str) -> list[NotificationOutbox]:
        """Return pending outbox rows for a website, oldest first."""
        with self.Session() as session:
            return (
                session.query(NotificationOutbox)
                .filter_by(website=website, status=OUTBOX_PENDING)
                .order_by(NotificationOutbox.created_at, NotificationOutbox.id)
                .all()
            )

    def mark_outbox_attempt(self, outbox_id: int) -> None:
        """Record a delivery attempt against an outbox row."""
        with self.Session() as session:
            row = session.get(NotificationOutbox, outbox_id)
            if row is not None:
                row.attempts += 1
                row.last_attempt_at = utcnow()
                session.commit()

    def complete_outbox(self, outbox_id: int, status: str = OUTBOX_DONE) -> None:
        """Mark an outbox row as done or expired."""
        if status not in (OUTBOX_DONE, OUTBOX_EXPIRED):
            raise ValueError(f"invalid outbox completion status: {status}")
        with self.Session() as session:
            row = session.get(NotificationOutbox, outbox_id)
            if row is not None:
                row.status = status
                row.completed_at = utcnow()
                session.commit()

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
        item.is_active = False
        item.delisted_at = utcnow()
        return {
            "Colour": 0xFF0000,
            "Title": item.Title,
            "Image": item.Image,
            "URL": item.URL,
            "Price": item.Price,
            "Stock": Stock.DELISTED.value,
            "Website": item.Website,
        }

    def _handle_stock_change(
        self, session: Any, item: AmiiboStock, new_datum: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply a stock-status transition (or relisting) and build its event."""
        log.info(
            f"Stock changed for {item.Title}: {item.Stock} -> {new_datum['Stock']}"
        )
        item.Stock = new_datum["Stock"]
        item.Colour = new_datum["Colour"]
        if self._prices_differ(item.Price, new_datum["Price"]):
            item.Price = new_datum["Price"]
        event = {
            "Colour": new_datum["Colour"],
            "Title": item.Title,
            "Image": item.Image,
            "URL": item.URL,
            "Price": new_datum["Price"],
            "Stock": new_datum["Stock"],
            "Website": item.Website,
        }
        if new_datum.get("Release"):
            event["Release"] = new_datum["Release"]
        return event

    @staticmethod
    def _record_stock_transition(item: AmiiboStock, now: datetime) -> None:
        """Count a stock status transition towards the item's flap count."""
        if item.last_flap_at is None or now - item.last_flap_at > timedelta(
            minutes=FLAP_WINDOW_MINUTES
        ):
            item.flap_count = 1
        else:
            item.flap_count += 1
        item.last_flap_at = now

    @staticmethod
    def _is_flapping(item: AmiiboStock, now: datetime) -> bool:
        """Whether the item has changed stock status often and recently enough."""
        return (
            item.flap_count >= FLAP_TRANSITION_THRESHOLD
            and item.last_flap_at is not None
            and now - item.last_flap_at <= timedelta(minutes=FLAP_WINDOW_MINUTES)
        )

    def _enqueue_event(
        self, session: Any, event: dict[str, Any], item: AmiiboStock
    ) -> bool:
        """Queue an event in the outbox unless the item's cooldown suppresses it.

        Urgent events (in stock, pre-order) are normally never suppressed:
        missing a restock is the worst outcome for users, so the cooldown only
        applies to the other statuses (out of stock, price change, delisted).
        Urgent events still update the item's last-notified bookkeeping.

        A flapping item (see ``_is_flapping``) is damped instead: its out of
        stock events are dropped, and its urgent events are held to the longer
        ``FLAP_ALERT_COOLDOWN_MINUTES`` cooldown instead of being sent every time.

        Runs inside the caller's transaction so that the state change and the
        pending notification are committed (or rolled back) together.
        """
        now = utcnow()
        status = event["Stock"]
        flapping = self._is_flapping(item, now)
        if flapping and status == Stock.OUT_OF_STOCK.value:
            log.info(f"Skipping notification for {item.Title} (Out of Stock, flapping)")
            return False
        cooldown = timedelta(
            minutes=FLAP_ALERT_COOLDOWN_MINUTES
            if flapping
            else NOTIFICATION_COOLDOWN_MINUTES
        )
        if (
            (status not in URGENT_STATUSES or flapping)
            and item.last_notified_at is not None
            and item.last_notified_status == status
            and now < item.last_notified_at + cooldown
        ):
            reason = "flapping, cooldown" if flapping else "cooldown"
            log.info(f"Skipping notification for {item.Title} ({status}, {reason})")
            return False
        item.last_notified_at = now
        item.last_notified_status = status
        session.add(
            NotificationOutbox(
                website=event["Website"],
                url=event["URL"],
                title=event["Title"],
                stock_status=status,
                price=event["Price"],
                image=event["Image"],
                colour=event["Colour"],
                release_date=event.get("Release"),
                status=OUTBOX_PENDING,
                attempts=0,
                created_at=now,
            )
        )
        return True

    def _add_new_items(
        self, session: Any, new_items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        added = []
        for datum in new_items:
            log.info(f"Adding {datum['Title']}")
            now = utcnow()
            amiibo = AmiiboStock(
                Website=datum["Website"],
                Title=datum["Title"],
                Price=datum["Price"],
                Stock=datum["Stock"],
                Colour=datum["Colour"],
                URL=datum["URL"],
                Image=datum["Image"],
                timestamp=now,
                is_active=True,
                first_seen_at=now,
                flap_count=0,
            )
            session.add(amiibo)
            # New items are never suppressed by the cooldown.
            self._enqueue_event(session, datum, amiibo)
            added.append(datum)
        return added

    def check_then_add_or_update_amiibo(
        self, data: list[dict[str, Any]], skip_delisting: bool = False
    ) -> list[dict[str, Any]]:
        """Apply a scrape to the database and enqueue notifications.

        Detected events (new item, stock change, price change, delisting) are
        written to the notification outbox in the same transaction as the state
        change. Returns the events that were enqueued (cooldown-suppressed
        events are applied to state but not returned).
        """
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

                existing_urls = {item.URL for item in existing_items}
                new_data_map = {datum["URL"]: datum for datum in data}

                for item in existing_items:
                    event: dict[str, Any] | None = None
                    if item.URL in new_data_map:
                        new_datum = new_data_map[item.URL]
                        item.missed_count = 0
                        if not item.is_active:
                            log.info(f"{item.Title} has returned to the listing")
                            item.is_active = True
                            item.delisted_at = None
                            event = self._handle_stock_change(session, item, new_datum)
                        elif new_datum["Stock"] != item.Stock:
                            self._record_stock_transition(item, utcnow())
                            event = self._handle_stock_change(session, item, new_datum)
                        elif self._prices_differ(item.Price, new_datum["Price"]):
                            event = self._handle_price_change(
                                session, item, new_datum["Price"]
                            )
                        if event is not None:
                            statistics["Updated"] += 1
                    elif not item.is_active:
                        # Already delisted: do not count misses or re-emit.
                        continue
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
                            event = self._handle_delisted_item(session, item)

                    if event is not None and self._enqueue_event(session, event, item):
                        output.append(event)

                new_items = [d for d in data if d["URL"] not in existing_urls]
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
