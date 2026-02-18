"""
Unit tests for database module.
"""

import pytest
from datetime import datetime, timedelta
from database import Database, LastScraped, AmiiboStock, ScrapingFailure
from config.config import Database as DatabaseConfig


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
        """Create test database instance."""
        import os

        db = Database(db_config)
        yield db
        # Cleanup: close engine and remove database file
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

    def test_update_or_insert_last_scraped(self, database):
        """Test updating last scraped timestamp."""
        stockist = "test.com"

        # First insert
        database.update_or_insert_last_scraped(stockist)

        # Verify it was inserted
        with database.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            assert record is not None
            assert record.stockist == stockist
            first_timestamp = record.timestamp

        # Update
        database.update_or_insert_last_scraped(stockist)

        # Verify it was updated
        with database.Session() as session:
            record = session.query(LastScraped).filter_by(stockist=stockist).first()
            assert record is not None
            assert record.timestamp >= first_timestamp

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
        updated_data = [initial_data[0]]
        result = database.check_then_add_or_update_amiibo(updated_data)

        # Should have one delisted item
        delisted = [r for r in result if r["Stock"] == "Delisted"]
        assert len(delisted) == 1
        assert delisted[0]["Title"] == "Test Amiibo 2"

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
