import logging
import re
from datetime import datetime
from typing import Any

import sqlalchemy as db
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config.config import Database as Database_
from stockist.stockist import Stock

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class AmiiboStock(Base):
    __tablename__ = "amiibo_stock"

    id: Mapped[int] = mapped_column(primary_key=True)
    Website: Mapped[str]
    Title: Mapped[str]
    Price: Mapped[str]
    Stock: Mapped[str]
    Colour: Mapped[str]
    URL: Mapped[str]
    Image: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(default=datetime.now)


class LastScraped(Base):
    __tablename__ = "last_scraped"

    stockist: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.now)


class ScrapingFailure(Base):
    """Track scraping failures to prevent false notifications."""

    __tablename__ = "scraping_failures"

    stockist: Mapped[str] = mapped_column(primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    last_failure: Mapped[datetime] = mapped_column(default=datetime.now)
    last_success: Mapped[datetime | None] = mapped_column(nullable=True)


class Database:
    def __init__(self, config: Database_) -> None:
        if config.engine == "postgres":
            engine_string = f"{config.username}:{config.password}@{config.host}:{config.port}/{config.name}"  # noqa: E501
            self.engine = db.create_engine("postgresql+psycopg2://" + engine_string)
        elif config.engine == "sqlite":
            self.engine = db.create_engine(
                "sqlite:///" + config.name + ".db?check_same_thread=false"
            )
        else:
            raise Exception(f"{config.engine} setup has not been defined")

        log.info(f"{config.engine} loaded")

        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        log.info("database tables loaded")

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

    def update_or_insert_last_scraped(self, stockist: str) -> None:
        """Update or insert last scraped timestamp for a stockist."""
        with self.Session() as session:
            existing = session.query(LastScraped).filter_by(stockist=stockist).first()
            if existing is None:
                session.add(LastScraped(stockist=stockist, timestamp=datetime.now()))
            else:
                existing.timestamp = datetime.now()
            session.commit()

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

    def _get_existing_items(self, website: str) -> list[AmiiboStock]:
        """Retrieve all existing items for a website."""
        with self.Session() as session:
            return session.query(AmiiboStock).filter_by(Website=website).all()

    def _handle_price_change(
        self, session: Any, item: AmiiboStock, new_price: str
    ) -> dict[str, Any]:
        """Handle price change for an item."""
        log.info(f"Price changed for {item.Title} " f"from {item.Price} to {new_price}")
        item.Price = new_price
        session.commit()
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
        """Handle delisted item."""
        log.info(f"{item.Title} is no longer listed")
        session.delete(item)
        session.commit()
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
        """Add new items to database."""
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
        session.commit()
        return added

    def check_then_add_or_update_amiibo(
        self, data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Check and update amiibo stock in database."""
        if not data:
            return []

        statistics = {"New": 0, "Updated": 0, "Deleted": 0}
        output = []
        website = data[0]["Website"]

        with self.Session() as session:
            existing_items = session.query(AmiiboStock).filter_by(Website=website).all()

            if not existing_items:
                # All items are new
                new_items = self._add_new_items(session, data)
                statistics["New"] = len(new_items)
                log.info(f"New items saved: {statistics['New']}")
                return data

            # Build URL map for existing items for faster lookup
            # Need to extract data before session closes
            existing_map = {
                item.URL: (item.id, item.Price, item.Title, item.Image)
                for item in existing_items
            }
            new_data_map = {datum["URL"]: datum for datum in data}

            # Handle price changes and matches
            for item in existing_items:
                if item.URL in new_data_map:
                    new_datum = new_data_map[item.URL]
                    if self.remove_currency(new_datum["Price"]) != self.remove_currency(
                        item.Price
                    ):
                        statistics["Updated"] += 1
                        output.append(
                            self._handle_price_change(session, item, new_datum["Price"])
                        )
                else:
                    # Item is delisted
                    statistics["Deleted"] += 1
                    output.append(self._handle_delisted_item(session, item))

            # Handle new items
            new_items = [d for d in data if d["URL"] not in existing_map]
            if new_items:
                added = self._add_new_items(session, new_items)
                output.extend(added)
                statistics["New"] = len(added)

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
        from datetime import timedelta

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
