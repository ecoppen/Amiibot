"""
Unit tests for database module.
"""

import pytest
from datetime import datetime, timedelta
from database import (
    Database,
    LastScraped,
    AmiiboStock,
    NotificationDelivery,
    NotificationOutbox,
    ScrapingFailure,
)
from config.config import DatabaseConfig


class TestDatabase:
    """Test database operations."""

    @pytest.fixture
    def db_config(self):
        """Create test database configuration."""
        import uuid

        # Use unique database name for each test to avoid conflicts
        return DatabaseConfig(
            engine="sqlite", name=f"test_amiibot_{uuid.uuid4().hex[:8]}"
        )

    @pytest.fixture
    def database(self, db_config):
        import os

        db = Database(db_config)
        db.ensure_schema()
        yield db
        db.engine.dispose()
        try:
            db_file = f"{db_config.name}.db"
            if os.path.exists(db_file):
                os.remove(db_file)
        except Exception:
            pass

    def test_database_initialization(self, database):
        """Test database initializes correctly."""
        assert database is not None
        assert database.engine is not None
        assert database.Session is not None

    def test_remove_currency_us_format(self, database):
        """Test currency removal for US format."""
        assert database.remove_currency("$19.99") == 19.99
        assert database.remove_currency("$1,234.56") == 1234.56

    def test_remove_currency_uk_format(self, database):
        """Test currency removal for UK format."""
        assert database.remove_currency("£19.99") == 19.99
        assert database.remove_currency("£1,234.56") == 1234.56

    def test_remove_currency_eu_format(self, database):
        """Test currency removal for EU format (comma as decimal)."""
        # EU format: 1.234,56 means 1234.56 (period as thousands, comma as decimal)
        result = database.remove_currency("€1.234,56")
        # Round to 2 decimal places to avoid floating point precision issues
        assert round(result, 2) == 1234.56

    def test_remove_currency_eu_format_simple(self, database):
        """Test currency removal for simple EU format."""
        # EU format with just comma as decimal
        assert round(database.remove_currency("€1,50"), 2) == 1.50
        assert round(database.remove_currency("€12,99"), 2) == 12.99

    def test_remove_currency_large_numbers(self, database):
        """Test currency removal with large numbers."""
        assert database.remove_currency("$12,345.67") == 12345.67
        assert round(database.remove_currency("€12.345,67"), 2) == 12345.67

    def test_remove_currency_no_symbol(self, database):
        """Test currency removal without symbol."""
        assert database.remove_currency("19.99") == 19.99
        assert database.remove_currency("1234.56") == 1234.56

    def test_remove_currency_invalid(self, database):
        """Test currency removal with invalid input."""
        with pytest.raises(ValueError):
            database.remove_currency("invalid")

    def test_validate_amiibo_data_valid(self, database):
        """Test data validation with valid data."""
        valid_data = {
            "Title": "Test Amiibo",
            "Price": "$19.99",
            "Stock": "In stock",
            "URL": "https://example.com/test",
            "Website": "example.com",
            "Image": "https://example.com/image.jpg",
            "Colour": 0x00FF00,
        }
        assert database._validate_amiibo_data(valid_data) is True

    def test_validate_amiibo_data_missing_field(self, database):
        """Test data validation with missing required field."""
        invalid_data = {
            "Title": "Test Amiibo",
            "Price": "$19.99",
            # Missing "Stock" field
            "URL": "https://example.com/test",
            "Website": "example.com",
            "Image": "https://example.com/image.jpg",
            "Colour": 0x00FF00,
        }
        with pytest.raises(ValueError, match="Missing required fields"):
            database._validate_amiibo_data(invalid_data)

    def test_validate_amiibo_data_empty_string(self, database):
        """Test data validation with empty string."""
        invalid_data = {
            "Title": "",  # Empty title
            "Price": "$19.99",
            "Stock": "In stock",
            "URL": "https://example.com/test",
            "Website": "example.com",
            "Image": "https://example.com/image.jpg",
            "Colour": 0x00FF00,
        }
        with pytest.raises(ValueError, match="empty string not allowed"):
            database._validate_amiibo_data(invalid_data)

    def test_validate_amiibo_data_wrong_type(self, database):
        """Test data validation with wrong data type."""
        invalid_data = {
            "Title": "Test Amiibo",
            "Price": "$19.99",
            "Stock": "In stock",
            "URL": "https://example.com/test",
            "Website": "example.com",
            "Image": "https://example.com/image.jpg",
            "Colour": "not_an_int",  # Should be int
        }
        with pytest.raises(ValueError, match="Invalid field types"):
            database._validate_amiibo_data(invalid_data)

    def test_record_scrape_attempt(self, database):
        stockist = "test.com"

        database.record_scrape_attempt(stockist)

        with database.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            assert record is not None
            assert record.stockist == stockist
            assert record.last_attempt_at is not None
            first_attempt = record.last_attempt_at

        database.record_scrape_attempt(stockist)

        with database.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            assert record is not None
            assert record.last_attempt_at >= first_attempt

    def test_get_statistics(self, database):
        """Test getting database statistics."""
        stats = database.get_statistics()
        assert isinstance(stats, dict)
        assert "total_amiibo" in stats
        assert "total_stockists" in stats
        assert isinstance(stats["total_amiibo"], int)
        assert isinstance(stats["total_stockists"], int)

    def test_record_scraping_failure(self, database):
        """Test recording scraping failures."""
        stockist = "test_failure.com"

        # First failure
        count = database.record_scraping_failure(stockist)
        assert count == 1

        # Second failure
        count = database.record_scraping_failure(stockist)
        assert count == 2

        # Third failure
        count = database.record_scraping_failure(stockist)
        assert count == 3

    def test_record_scraping_success(self, database):
        """Test recording scraping success after failures."""
        stockist = "test_recovery.com"

        # Record some failures
        database.record_scraping_failure(stockist)
        database.record_scraping_failure(stockist)
        assert database.get_consecutive_failures(stockist) == 2

        # Record success
        database.record_scraping_success(stockist)

        # Verify failures reset
        assert database.get_consecutive_failures(stockist) == 0

    def test_get_consecutive_failures_nonexistent(self, database):
        """Test getting failures for non-existent stockist."""
        count = database.get_consecutive_failures("nonexistent.com")
        assert count == 0

    def test_check_then_add_or_update_amiibo_empty_data(self, database):
        """Test with empty data list."""
        result = database.check_then_add_or_update_amiibo([])
        assert result == []

    def test_check_then_add_or_update_amiibo_new_items(self, database):
        """Test adding new items."""
        data = [
            {
                "Title": "Test Amiibo 1",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/1",
                "Website": "test.com",
                "Image": "https://test.com/img1.jpg",
                "Colour": 0x00FF00,
            },
            {
                "Title": "Test Amiibo 2",
                "Price": "$24.99",
                "Stock": "In stock",
                "URL": "https://test.com/2",
                "Website": "test.com",
                "Image": "https://test.com/img2.jpg",
                "Colour": 0x00FF00,
            },
        ]

        result = database.check_then_add_or_update_amiibo(data)
        assert len(result) == 2

        # Verify items are in database
        with database.Session() as session:
            items = session.query(AmiiboStock).filter_by(Website="test.com").all()
            assert len(items) == 2

    def test_check_then_add_or_update_amiibo_price_change(self, database):
        """Test price change detection."""
        # Add initial item
        initial_data = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/price",
                "Website": "test_price.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        database.check_then_add_or_update_amiibo(initial_data)

        # Update with new price
        updated_data = [
            {
                "Title": "Test Amiibo",
                "Price": "$24.99",
                "Stock": "In stock",
                "URL": "https://test.com/price",
                "Website": "test_price.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        result = database.check_then_add_or_update_amiibo(updated_data)

        assert len(result) == 1
        assert result[0]["Stock"] == "Price change"
        assert result[0]["Price"] == "$24.99"

    def test_check_then_add_or_update_amiibo_delisted(self, database):
        """Test delisted item detection."""
        # Add initial items
        initial_data = [
            {
                "Title": "Test Amiibo 1",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/del1",
                "Website": "test_delist.com",
                "Image": "https://test.com/img1.jpg",
                "Colour": 0x00FF00,
            },
            {
                "Title": "Test Amiibo 2",
                "Price": "$24.99",
                "Stock": "In stock",
                "URL": "https://test.com/del2",
                "Website": "test_delist.com",
                "Image": "https://test.com/img2.jpg",
                "Colour": 0x00FF00,
            },
        ]
        database.check_then_add_or_update_amiibo(initial_data)

        # Update with only one item (second is delisted)
        # First miss: not delisted yet (grace period = 2)
        updated_data = [initial_data[0]]
        result = database.check_then_add_or_update_amiibo(updated_data)
        delisted = [r for r in result if r["Stock"] == "Delisted"]
        assert len(delisted) == 0, "Should not delist on first miss"

        # Second miss: now it should be delisted
        result = database.check_then_add_or_update_amiibo(updated_data)
        delisted = [r for r in result if r["Stock"] == "Delisted"]
        assert len(delisted) == 1
        assert delisted[0]["Title"] == "Test Amiibo 2"

    def test_delisting_grace_period_reset_on_reappearance(self, database):
        """Test that missed_count resets when a previously-missing item reappears."""
        initial_data = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/grace",
                "Website": "test_grace.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        database.check_then_add_or_update_amiibo(initial_data)

        # First miss: item missing from scrape
        result = database.check_then_add_or_update_amiibo([])
        delisted = [r for r in result if r["Stock"] == "Delisted"]
        assert len(delisted) == 0, "Should not delist on first miss"

        # Item reappears — missed_count should reset to 0
        database.check_then_add_or_update_amiibo(initial_data)
        # Should still exist in DB, not be treated as a new item or delisted
        with database.Session() as session:
            item = (
                session.query(AmiiboStock)
                .filter_by(URL="https://test.com/grace")
                .first()
            )
            assert item is not None
            assert item.missed_count == 0

    def test_skip_delisting_parameter(self, database):
        """Test that skip_delisting=True prevents delisting entirely."""
        initial_data = [
            {
                "Title": "Test Amiibo 1",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/skip1",
                "Website": "test_skip.com",
                "Image": "https://test.com/img1.jpg",
                "Colour": 0x00FF00,
            },
            {
                "Title": "Test Amiibo 2",
                "Price": "$24.99",
                "Stock": "In stock",
                "URL": "https://test.com/skip2",
                "Website": "test_skip.com",
                "Image": "https://test.com/img2.jpg",
                "Colour": 0x00FF00,
            },
        ]
        database.check_then_add_or_update_amiibo(initial_data)

        # Run multiple times with skip_delisting=True — item should never be delisted
        updated_data = [initial_data[0]]
        for _ in range(5):
            result = database.check_then_add_or_update_amiibo(
                updated_data, skip_delisting=True
            )
            delisted = [r for r in result if r["Stock"] == "Delisted"]
            assert len(delisted) == 0, "skip_delisting should prevent delisting"

        # Verify missed_count was NOT incremented
        with database.Session() as session:
            item = (
                session.query(AmiiboStock)
                .filter_by(URL="https://test.com/skip2")
                .first()
            )
            assert item is not None
            assert item.missed_count == 0

    def test_get_last_healthy_count(self, database):
        stockist = "test_count.com"
        assert database.get_last_healthy_count(stockist) == 0

        database.record_healthy_scrape(stockist, 42)
        assert database.get_last_healthy_count(stockist) == 42

    def test_get_consecutive_unhealthy_obs(self, database):
        stockist = "test_unhealthy.com"
        assert database.get_consecutive_unhealthy_obs(stockist) == 0

        count = database.record_unhealthy_scrape(stockist)
        assert count == 1
        assert database.get_consecutive_unhealthy_obs(stockist) == 1

        count = database.record_unhealthy_scrape(stockist)
        assert count == 2
        assert database.get_consecutive_unhealthy_obs(stockist) == 2

    def test_healthy_scrape_resets_unhealthy_obs(self, database):
        stockist = "test_reset.com"

        database.record_unhealthy_scrape(stockist)
        database.record_unhealthy_scrape(stockist)
        assert database.get_consecutive_unhealthy_obs(stockist) == 2

        database.record_healthy_scrape(stockist, 10)
        assert database.get_consecutive_unhealthy_obs(stockist) == 0
        assert database.get_last_healthy_count(stockist) == 10

    def test_record_healthy_scrape_sets_last_success(self, database):
        stockist = "test_success.com"

        database.record_healthy_scrape(stockist, 25)

        with database.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            assert record is not None
            assert record.last_success_at is not None
            assert record.last_healthy_count == 25

    def test_notification_suppression_cooldown(self, database):
        """Test that notifications are suppressed within the cooldown period."""
        data = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/notify",
                "Website": "test_notify.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        database.check_then_add_or_update_amiibo(data)

        # Enqueueing the new item's event already recorded a notification
        assert database.should_suppress_notification(
            "https://test.com/notify", "test_notify.com", "In stock"
        )

        # Clear it, then record a notification explicitly
        with database.Session() as session:
            item = session.query(AmiiboStock).one()
            item.last_notified_at = None
            item.last_notified_status = None
            session.commit()
        assert not database.should_suppress_notification(
            "https://test.com/notify", "test_notify.com", "In stock"
        )
        database.record_notification(
            "https://test.com/notify", "test_notify.com", "In stock"
        )

        # Should now be suppressed (same status within cooldown)
        assert database.should_suppress_notification(
            "https://test.com/notify", "test_notify.com", "In stock"
        )

        # Different status should NOT be suppressed
        assert not database.should_suppress_notification(
            "https://test.com/notify", "test_notify.com", "Delisted"
        )

    def test_notification_suppression_nonexistent_item(self, database):
        """Test that suppression check returns False for items not in DB."""
        assert not database.should_suppress_notification(
            "https://nonexistent.com/item", "no_site.com", "In stock"
        )

    def test_cleanup_old_records(self, database):
        """Test cleaning up old records."""
        # Add an old item manually
        with database.Session() as session:
            old_item = AmiiboStock(
                Website="old.com",
                Title="Old Amiibo",
                Price="$19.99",
                Stock="In stock",
                Colour="0x00FF00",
                URL="https://old.com/1",
                Image="https://old.com/img.jpg",
                timestamp=datetime.now() - timedelta(days=60),
            )
            session.add(old_item)

            recent_item = AmiiboStock(
                Website="recent.com",
                Title="Recent Amiibo",
                Price="$19.99",
                Stock="In stock",
                Colour="0x00FF00",
                URL="https://recent.com/1",
                Image="https://recent.com/img.jpg",
                timestamp=datetime.now(),
            )
            session.add(recent_item)
            session.commit()

        # Clean up records older than 30 days
        deleted = database.cleanup_old_records(days_old=30)
        assert deleted >= 1

        # Verify recent item still exists
        with database.Session() as session:
            items = session.query(AmiiboStock).filter_by(Website="recent.com").all()
            assert len(items) == 1

    def test_get_existing_items(self, database):
        """Test getting existing items for a website."""
        # Add some items
        data = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://existing.com/1",
                "Website": "existing.com",
                "Image": "https://existing.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        database.check_then_add_or_update_amiibo(data)

        # Get existing items
        items = database._get_existing_items("existing.com")
        assert len(items) >= 1
        assert items[0].Website == "existing.com"

    def test_scraping_failure_timestamp_updates(self, database):
        """Test that failure timestamps are updated correctly."""
        stockist = "test_timestamp.com"

        # Record first failure
        database.record_scraping_failure(stockist)

        with database.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            first_failure_time = failure.last_failure

        # Wait a tiny bit and record another failure
        import time

        time.sleep(0.01)

        database.record_scraping_failure(stockist)

        with database.Session() as session:
            failure = (
                session.query(ScrapingFailure).filter_by(stockist=stockist).first()
            )
            second_failure_time = failure.last_failure

        assert second_failure_time > first_failure_time

    def test_record_delivery_and_was_delivered(self, database):
        """Test delivery recording and lookup."""
        from result import DeliveryStatus

        key = "outbox:1"

        assert database.was_delivered_to(key, "discord") is False

        database.record_delivery(
            idempotency_key=key,
            website="test.com",
            url="https://test.com/1",
            title="Test",
            stock_status="In stock",
            messenger_name="discord",
            delivery_status=DeliveryStatus.SUCCESS.value,
        )

        assert database.was_delivered_to(key, "discord") is True
        assert database.was_delivered_to(key, "telegram") is False

    def test_record_delivery_is_idempotent(self, database):
        """Test duplicate deliveries are not recorded twice."""
        key = "same-key"

        database.record_delivery(
            idempotency_key=key,
            website="test.com",
            url="https://test.com/1",
            title="Test",
            stock_status="In stock",
            messenger_name="discord",
            delivery_status="Success",
        )
        database.record_delivery(
            idempotency_key=key,
            website="test.com",
            url="https://test.com/1",
            title="Test",
            stock_status="In stock",
            messenger_name="discord",
            delivery_status="Success",
        )

        from database import NotificationDelivery

        with database.Session() as session:
            count = (
                session.query(NotificationDelivery)
                .filter_by(idempotency_key=key, messenger_name="discord")
                .count()
            )
            assert count == 1

    def test_was_delivered_false_for_failed_status(self, database):
        """Test failed deliveries do not count as delivered."""
        from result import DeliveryStatus

        key = "failed-key"

        database.record_delivery(
            idempotency_key=key,
            website="test.com",
            url="https://test.com/1",
            title="Test",
            stock_status="In stock",
            messenger_name="discord",
            delivery_status=DeliveryStatus.PERMANENT_FAILURE.value,
        )

        assert database.was_delivered_to(key, "discord") is False

    def test_run_migrations_is_idempotent(self, database):
        """Test migrations can run multiple times without error."""
        database._run_migrations()
        database._run_migrations()

        with database.Session() as session:
            item = session.query(AmiiboStock).first()
            assert item is None or item.Website is not None


def _datum(url="https://t.com/1", stock="In stock", price="$19.99", colour=0x00FF00):
    return {
        "Title": f"Amiibo {url[-1]}",
        "Price": price,
        "Stock": stock,
        "URL": url,
        "Website": "t.com",
        "Image": "https://t.com/img.jpg",
        "Colour": colour,
    }


class TestOutboxChangeDetection:
    """Change detection, atomic outbox enqueueing and cooldown behaviour."""

    @pytest.fixture
    def database(self):
        import os
        import uuid

        config = DatabaseConfig(
            engine="sqlite", name=f"test_outbox_{uuid.uuid4().hex[:8]}"
        )
        db = Database(config)
        db.ensure_schema()
        yield db
        db.engine.dispose()
        if os.path.exists(f"{config.name}.db"):
            os.remove(f"{config.name}.db")

    @staticmethod
    def _outbox(database):
        with database.Session() as session:
            return (
                session.query(NotificationOutbox).order_by(NotificationOutbox.id).all()
            )

    @staticmethod
    def _item(database, url="https://t.com/1"):
        with database.Session() as session:
            return session.query(AmiiboStock).filter_by(URL=url).one()

    @staticmethod
    def _expire_cooldown(database):
        with database.Session() as session:
            for item in session.query(AmiiboStock).all():
                if item.last_notified_at:
                    item.last_notified_at = datetime.now() - timedelta(hours=2)
            session.commit()

    def test_new_items_enqueue_outbox_rows(self, database):
        events = database.check_then_add_or_update_amiibo(
            [_datum("https://t.com/1"), _datum("https://t.com/2")]
        )
        assert len(events) == 2
        rows = self._outbox(database)
        assert len(rows) == 2
        row = rows[0]
        assert row.status == "pending"
        assert row.attempts == 0
        assert row.price == "$19.99"
        assert row.image == "https://t.com/img.jpg"
        assert row.colour == 0x00FF00
        assert row.stock_status == "In stock"
        assert row.website == "t.com"

    def test_new_item_on_existing_website_enqueues(self, database):
        database.check_then_add_or_update_amiibo([_datum("https://t.com/1")])
        events = database.check_then_add_or_update_amiibo(
            [_datum("https://t.com/1"), _datum("https://t.com/2")]
        )
        assert [e["URL"] for e in events] == ["https://t.com/2"]
        assert len(self._outbox(database)) == 2

    def test_restock_emits_in_stock_event(self, database):
        database.check_then_add_or_update_amiibo(
            [_datum(stock="Out of Stock", colour=0xFF0000)]
        )
        events = database.check_then_add_or_update_amiibo([_datum(stock="In stock")])

        assert len(events) == 1
        assert events[0]["Stock"] == "In stock"
        assert events[0]["Colour"] == 0x00FF00
        assert events[0]["Price"] == "$19.99"
        rows = self._outbox(database)
        assert [r.stock_status for r in rows] == ["Out of Stock", "In stock"]
        assert rows[1].colour == 0x00FF00
        item = self._item(database)
        assert item.Stock == "In stock"
        assert int(item.Colour) == 0x00FF00

    def test_sellout_emits_out_of_stock_event(self, database):
        database.check_then_add_or_update_amiibo([_datum(stock="In stock")])
        events = database.check_then_add_or_update_amiibo(
            [_datum(stock="Out of Stock", colour=0xFF0000)]
        )
        assert len(events) == 1
        assert events[0]["Stock"] == "Out of Stock"
        assert events[0]["Colour"] == 0xFF0000
        assert self._item(database).Stock == "Out of Stock"
        assert len(self._outbox(database)) == 2

    def test_unchanged_item_emits_nothing(self, database):
        database.check_then_add_or_update_amiibo([_datum()])
        assert database.check_then_add_or_update_amiibo([_datum()]) == []
        assert len(self._outbox(database)) == 1

    def test_stock_and_price_change_emit_single_event(self, database):
        database.check_then_add_or_update_amiibo(
            [_datum(stock="Out of Stock", price="$19.99")]
        )
        events = database.check_then_add_or_update_amiibo(
            [_datum(stock="In stock", price="$24.99")]
        )
        assert len(events) == 1
        assert events[0]["Stock"] == "In stock"
        assert events[0]["Price"] == "$24.99"
        item = self._item(database)
        assert item.Stock == "In stock"
        assert item.Price == "$24.99"
        assert len(self._outbox(database)) == 2

    def test_two_price_changes_produce_two_distinct_outbox_rows(self, database):
        database.check_then_add_or_update_amiibo([_datum(price="$19.99")])
        database.check_then_add_or_update_amiibo([_datum(price="$24.99")])
        self._expire_cooldown(database)
        events = database.check_then_add_or_update_amiibo([_datum(price="$29.99")])

        assert len(events) == 1
        rows = [r for r in self._outbox(database) if r.stock_status == "Price change"]
        assert [r.price for r in rows] == ["$24.99", "$29.99"]
        assert len({f"outbox:{r.id}" for r in rows}) == 2

    def test_price_change_within_cooldown_is_suppressed(self, database):
        database.check_then_add_or_update_amiibo([_datum(price="$19.99")])
        database.check_then_add_or_update_amiibo([_datum(price="$24.99")])
        events = database.check_then_add_or_update_amiibo([_datum(price="$29.99")])

        assert events == []
        # State is still tracked even though no notification was queued.
        assert self._item(database).Price == "$29.99"
        assert (
            len([r for r in self._outbox(database) if r.stock_status == "Price change"])
            == 1
        )

    def test_restock_sellout_restock_emits_each_transition(self, database):
        database.check_then_add_or_update_amiibo([_datum(stock="Out of Stock")])
        statuses = []
        for stock in ["In stock", "Out of Stock", "In stock"]:
            self._expire_cooldown(database)
            events = database.check_then_add_or_update_amiibo([_datum(stock=stock)])
            statuses.extend(e["Stock"] for e in events)
        assert statuses == ["In stock", "Out of Stock", "In stock"]

    def test_in_stock_never_suppressed_by_cooldown(self, database):
        database.check_then_add_or_update_amiibo([_datum(stock="In stock")])
        returned = []
        for stock in ["Out of Stock", "In stock"]:
            returned.extend(
                database.check_then_add_or_update_amiibo([_datum(stock=stock)])
            )

        assert [e["Stock"] for e in returned] == ["Out of Stock", "In stock"]
        rows = self._outbox(database)
        assert [r.stock_status for r in rows] == [
            "In stock",
            "Out of Stock",
            "In stock",
        ]
        item = self._item(database)
        assert item.last_notified_status == "In stock"
        assert item.last_notified_at is not None

    def test_stock_flap_within_cooldown_tracks_state_and_notifies(self, database):
        database.check_then_add_or_update_amiibo([_datum(stock="Out of Stock")])
        returned = []
        for stock in ["In stock", "Out of Stock", "In stock", "Out of Stock"]:
            events = database.check_then_add_or_update_amiibo([_datum(stock=stock)])
            returned.extend(e["Stock"] for e in events)
            # Stored state follows the scrape whether or not an event was queued.
            assert self._item(database).Stock == stock

        # Each in-stock event records "In stock" as the last notified status, so
        # no Out of Stock transition here repeats the last notified status.
        assert returned == ["In stock", "Out of Stock", "In stock", "Out of Stock"]
        assert len(self._outbox(database)) == 5

    def test_out_of_stock_still_subject_to_cooldown(self, database):
        database.check_then_add_or_update_amiibo([_datum(stock="Out of Stock")])
        event = _datum(stock="Out of Stock")
        in_stock_event = _datum(stock="In stock")

        with database.Session() as session:
            item = session.query(AmiiboStock).one()
            # Same status within the cooldown is suppressed ...
            assert item.last_notified_status == "Out of Stock"
            assert database._enqueue_event(session, event, item) is False
            # ... but an in-stock event is not, even when it repeats.
            item.last_notified_status = "In stock"
            assert database._enqueue_event(session, in_stock_event, item) is True
            assert database._enqueue_event(session, in_stock_event, item) is True
            session.commit()

        assert len(self._outbox(database)) == 3

    def test_new_item_not_suppressed_by_cooldown(self, database):
        database.check_then_add_or_update_amiibo([_datum("https://t.com/1")])
        events = database.check_then_add_or_update_amiibo(
            [_datum("https://t.com/1"), _datum("https://t.com/2")]
        )
        assert len(events) == 1

    def test_delisted_item_emits_exactly_one_delisted_event(self, database):
        keep = _datum("https://t.com/1")
        gone = _datum("https://t.com/2")
        database.check_then_add_or_update_amiibo([keep, gone])

        delisted = []
        for _ in range(6):
            events = database.check_then_add_or_update_amiibo([keep])
            delisted.extend(e for e in events if e["Stock"] == "Delisted")

        assert len(delisted) == 1
        assert delisted[0]["URL"] == "https://t.com/2"
        item = self._item(database, "https://t.com/2")
        assert item.is_active is False
        assert item.delisted_at is not None
        # missed_count is no longer incremented once the item is inactive.
        assert item.missed_count == 2
        assert (
            len([r for r in self._outbox(database) if r.stock_status == "Delisted"])
            == 1
        )

    def test_delisted_item_reappearing_is_reactivated_and_emits(self, database):
        keep = _datum("https://t.com/1")
        gone = _datum("https://t.com/2")
        database.check_then_add_or_update_amiibo([keep, gone])
        for _ in range(3):
            database.check_then_add_or_update_amiibo([keep])

        events = database.check_then_add_or_update_amiibo(
            [keep, _datum("https://t.com/2", stock="Out of Stock", colour=0xFF0000)]
        )

        assert len(events) == 1
        assert events[0]["URL"] == "https://t.com/2"
        assert events[0]["Stock"] == "Out of Stock"
        assert events[0]["Colour"] == 0xFF0000
        item = self._item(database, "https://t.com/2")
        assert item.is_active is True
        assert item.delisted_at is None
        assert item.missed_count == 0
        assert item.Stock == "Out of Stock"

    def test_reappearing_in_stock_item_emits_in_stock(self, database):
        keep = _datum("https://t.com/1")
        gone = _datum("https://t.com/2")
        database.check_then_add_or_update_amiibo([keep, gone])
        for _ in range(2):
            database.check_then_add_or_update_amiibo([keep])
        events = database.check_then_add_or_update_amiibo([keep, gone])
        assert [e["Stock"] for e in events] == ["In stock"]

    def test_skip_delisting_does_not_touch_inactive_items(self, database):
        keep = _datum("https://t.com/1")
        gone = _datum("https://t.com/2")
        database.check_then_add_or_update_amiibo([keep, gone])
        for _ in range(2):
            database.check_then_add_or_update_amiibo([keep])
        events = database.check_then_add_or_update_amiibo([keep], skip_delisting=True)
        assert events == []

    def test_state_and_outbox_roll_back_together(self, database):
        database.check_then_add_or_update_amiibo(
            [_datum("https://t.com/1", stock="Out of Stock"), _datum("https://t.com/2")]
        )
        before = len(self._outbox(database))
        with pytest.raises(ValueError):
            database.check_then_add_or_update_amiibo(
                [
                    _datum("https://t.com/1", stock="In stock"),
                    _datum("https://t.com/2", price="not a price"),
                ]
            )
        assert len(self._outbox(database)) == before
        assert self._item(database, "https://t.com/1").Stock == "Out of Stock"


class TestOutboxStorage:
    @pytest.fixture
    def database(self):
        import os
        import uuid

        config = DatabaseConfig(
            engine="sqlite", name=f"test_outbox_store_{uuid.uuid4().hex[:8]}"
        )
        db = Database(config)
        db.ensure_schema()
        yield db
        db.engine.dispose()
        if os.path.exists(f"{config.name}.db"):
            os.remove(f"{config.name}.db")

    @staticmethod
    def _add_row(database, website="t.com", created_at=None, status="pending"):
        with database.Session() as session:
            row = NotificationOutbox(
                website=website,
                url="https://t.com/1",
                title="T",
                stock_status="In stock",
                price="$1",
                image="img",
                colour=1,
                status=status,
                created_at=created_at or datetime.now(),
            )
            session.add(row)
            session.commit()
            return row.id

    def test_get_pending_outbox_oldest_first_and_filtered(self, database):
        newer = self._add_row(database, created_at=datetime.now())
        older = self._add_row(database, created_at=datetime.now() - timedelta(hours=1))
        self._add_row(database, website="other.com")
        self._add_row(database, status="done")

        rows = database.get_pending_outbox("t.com")
        assert [r.id for r in rows] == [older, newer]

    def test_mark_outbox_attempt(self, database):
        row_id = self._add_row(database)
        database.mark_outbox_attempt(row_id)
        database.mark_outbox_attempt(row_id)
        row = database.get_pending_outbox("t.com")[0]
        assert row.attempts == 2
        assert row.last_attempt_at is not None

    def test_mark_outbox_attempt_unknown_id_is_noop(self, database):
        database.mark_outbox_attempt(9999)
        database.complete_outbox(9999)

    def test_complete_outbox_done_and_expired(self, database):
        done_id = self._add_row(database)
        expired_id = self._add_row(database)
        database.complete_outbox(done_id, "done")
        database.complete_outbox(expired_id, "expired")

        assert database.get_pending_outbox("t.com") == []
        with database.Session() as session:
            done = session.get(NotificationOutbox, done_id)
            expired = session.get(NotificationOutbox, expired_id)
            assert done.status == "done" and done.completed_at is not None
            assert expired.status == "expired" and expired.completed_at is not None

    def test_complete_outbox_rejects_pending(self, database):
        row_id = self._add_row(database)
        with pytest.raises(ValueError):
            database.complete_outbox(row_id, "pending")

    def test_record_delivery_upserts_transient_to_success(self, database):
        kwargs = dict(
            idempotency_key="outbox:1",
            website="t.com",
            url="https://t.com/1",
            title="T",
            stock_status="In stock",
            messenger_name="discord",
        )
        database.record_delivery(delivery_status="transient_failure", **kwargs)
        assert database.was_delivered_to("outbox:1", "discord") is False
        assert (
            database.get_delivery_status("outbox:1", "discord") == "transient_failure"
        )

        database.record_delivery(delivery_status="success", **kwargs)
        assert database.was_delivered_to("outbox:1", "discord") is True
        assert database.get_delivery_status("outbox:1", "discord") == "success"
        assert database.get_delivery_status("outbox:1", "telegram") is None
        with database.Session() as session:
            assert session.query(NotificationDelivery).count() == 1


class TestOutboxMigration:
    NEW_COLUMNS = {
        "price",
        "image",
        "colour",
        "status",
        "attempts",
        "last_attempt_at",
        "completed_at",
    }

    @pytest.fixture
    def database(self):
        import os
        import uuid

        import sqlalchemy as sa

        config = DatabaseConfig(
            engine="sqlite", name=f"test_outbox_mig_{uuid.uuid4().hex[:8]}"
        )
        db = Database(config)
        db.ensure_schema()
        with db.engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE notification_outbox"))
            conn.execute(
                sa.text(
                    "CREATE TABLE notification_outbox ("
                    "id INTEGER NOT NULL PRIMARY KEY, website VARCHAR NOT NULL, "
                    "url VARCHAR NOT NULL, title VARCHAR NOT NULL, "
                    "stock_status VARCHAR NOT NULL, created_at DATETIME NOT NULL)"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO notification_outbox VALUES "
                    "(1, 'w', 'u', 't', 'In stock', '2026-01-01 00:00:00')"
                )
            )
        yield db
        db.engine.dispose()
        if os.path.exists(f"{config.name}.db"):
            os.remove(f"{config.name}.db")

    def _columns(self, database):
        import sqlalchemy as sa

        with database.engine.connect() as conn:
            return {
                row[1]
                for row in conn.execute(
                    sa.text("PRAGMA table_info(notification_outbox)")
                )
            }

    def test_old_schema_gets_new_columns_and_is_idempotent(self, database):
        assert not (self.NEW_COLUMNS & self._columns(database))

        database._run_migrations()
        assert self.NEW_COLUMNS <= self._columns(database)

        database._run_migrations()
        assert self.NEW_COLUMNS <= self._columns(database)

        with database.Session() as session:
            row = session.query(NotificationOutbox).one()
            assert row.status == "pending"
            assert row.attempts == 0
            assert row.price == ""

    def test_migrated_table_is_usable(self, database):
        database._run_migrations()
        database.check_then_add_or_update_amiibo([_datum()])
        assert len(database.get_pending_outbox("t.com")) == 1
        assert len(database.get_pending_outbox("w")) == 1
