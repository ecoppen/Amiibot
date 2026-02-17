"""
Unit tests for database module.
"""

import pytest
from database import Database, LastScraped
from config.config import Database as DatabaseConfig


class TestDatabase:
    """Test database operations."""

    @pytest.fixture
    def db_config(self):
        """Create test database configuration."""
        return DatabaseConfig(engine="sqlite", name="test_amiibot")

    @pytest.fixture
    def database(self, db_config):
        """Create test database instance."""
        db = Database(db_config)
        yield db
        # Cleanup: close engine to prevent ResourceWarning
        db.engine.dispose()

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
