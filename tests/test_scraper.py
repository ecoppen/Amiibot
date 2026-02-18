"""
Unit tests for scraper module.
"""

import pytest
from unittest.mock import Mock, patch
import requests
from scraper import Scraper


class TestScraper:
    """Test Scraper class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return Mock()

    @pytest.fixture
    def mock_database(self):
        """Create mock database."""
        db = Mock()
        db.record_scraping_failure.return_value = 1
        db.record_scraping_success.return_value = None
        db.get_consecutive_failures.return_value = 0
        db.update_or_insert_last_scraped.return_value = None
        db._validate_amiibo_data.return_value = True
        db.check_then_add_or_update_amiibo.return_value = []
        return db

    @pytest.fixture
    def mock_stockist(self):
        """Create mock stockist."""
        stockist = Mock()
        stockist.name = "test.com"
        stockist.messengers = ["test_messenger"]
        stockist.get_amiibo.return_value = []
        return stockist

    @pytest.fixture
    def mock_messenger(self):
        """Create mock messenger."""
        messenger = Mock()
        messenger.name = "test_messenger"
        messenger.send_embed_message.return_value = None
        return messenger

    @pytest.fixture
    def mock_stockists(self, mock_stockist, mock_messenger):
        """Create mock stockists manager."""
        stockists = Mock()
        stockists.all_stockists = [mock_stockist]

        messenger_manager = Mock()
        messenger_manager.all_messengers = [mock_messenger]
        stockists.messengers = messenger_manager

        return stockists

    @pytest.fixture
    def scraper(self, mock_config, mock_stockists, mock_database):
        """Create scraper instance."""
        return Scraper(
            config=mock_config,
            stockists=mock_stockists,
            database=mock_database,
        )

    def test_scraper_initialization(
        self, scraper, mock_config, mock_stockists, mock_database
    ):
        """Test scraper initializes correctly."""
        assert scraper.config == mock_config
        assert scraper.stockists == mock_stockists
        assert scraper.database == mock_database
        assert scraper.messengers == mock_stockists.messengers

    @patch("time.sleep")
    def test_scrape_success_first_attempt(self, mock_sleep, scraper):
        """Test successful scrape on first attempt."""
        scraper.scrape_cycle = Mock()

        scraper.scrape()

        scraper.scrape_cycle.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_scrape_timeout_with_retry(self, mock_sleep, scraper):
        """Test scrape with timeout and retry."""
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            None,  # Success on second attempt
        ]

        scraper.scrape()

        assert scraper.scrape_cycle.call_count == 2
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_scrape_max_retries_timeout(self, mock_sleep, scraper):
        """Test scrape with max retries on timeout."""
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = requests.exceptions.Timeout("Timeout")

        scraper.scrape()

        assert scraper.scrape_cycle.call_count == 3  # MAX_RETRY_ATTEMPTS
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    def test_scrape_too_many_redirects(self, mock_sleep, scraper):
        """Test scrape with too many redirects (no retry)."""
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = requests.exceptions.TooManyRedirects(
            "Redirects"
        )

        scraper.scrape()

        scraper.scrape_cycle.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_scrape_request_exception_with_retry(self, mock_sleep, scraper):
        """Test scrape with request exception and retry."""
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = [
            requests.exceptions.RequestException("Error"),
            None,
        ]

        scraper.scrape()

        assert scraper.scrape_cycle.call_count == 2
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_scrape_unexpected_error(self, mock_sleep, scraper):
        """Test scrape with unexpected error (no retry)."""
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = ValueError("Unexpected error")

        scraper.scrape()

        scraper.scrape_cycle.assert_called_once()
        mock_sleep.assert_not_called()

    def test_scrape_cycle_empty_stockists(self, mock_config, mock_database):
        """Test scrape cycle with no stockists."""
        empty_stockists = Mock()
        empty_stockists.all_stockists = []
        empty_stockists.messengers = Mock()
        empty_stockists.messengers.all_messengers = []

        scraper = Scraper(
            config=mock_config,
            stockists=empty_stockists,
            database=mock_database,
        )

        # Should not raise error
        scraper.scrape_cycle()

    def test_scrape_cycle_success_no_items(self, scraper, mock_database):
        """Test scrape cycle with no items returned."""
        scraper.scrape_cycle()

        # Should record failure for empty results
        mock_database.record_scraping_failure.assert_called_once()
        mock_database.update_or_insert_last_scraped.assert_called_once()

    def test_scrape_cycle_success_with_items(
        self, scraper, mock_stockist, mock_database
    ):
        """Test scrape cycle with items returned."""
        items = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/1",
                "Website": "test.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        mock_stockist.get_amiibo.return_value = items
        mock_database.check_then_add_or_update_amiibo.return_value = []

        scraper.scrape_cycle()

        mock_database.record_scraping_success.assert_called_once_with("test.com")
        mock_database.update_or_insert_last_scraped.assert_called_once()
        mock_database._validate_amiibo_data.assert_called_once()

    def test_scrape_cycle_with_invalid_data(
        self, scraper, mock_stockist, mock_database
    ):
        """Test scrape cycle with invalid data."""
        items = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
            }
        ]
        mock_stockist.get_amiibo.return_value = items
        mock_database._validate_amiibo_data.side_effect = ValueError("Invalid data")

        scraper.scrape_cycle()

        # Should skip database update for invalid data
        mock_database.check_then_add_or_update_amiibo.assert_not_called()

    def test_scrape_cycle_with_notifications(
        self, scraper, mock_stockist, mock_database, mock_messenger
    ):
        """Test scrape cycle with notifications sent."""
        items = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/1",
                "Website": "test.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        mock_stockist.get_amiibo.return_value = items
        mock_database.check_then_add_or_update_amiibo.return_value = items

        scraper.scrape_cycle()

        mock_messenger.send_embed_message.assert_called_once()

    def test_scrape_cycle_stockist_exception(
        self, scraper, mock_stockist, mock_database
    ):
        """Test scrape cycle when stockist raises exception."""
        mock_stockist.get_amiibo.side_effect = Exception("Scraping error")

        scraper.scrape_cycle()

        # Should record failure and continue
        mock_database.record_scraping_failure.assert_called_once_with("test.com")
        mock_database.update_or_insert_last_scraped.assert_called_once()

    def test_scrape_cycle_multiple_stockists(self, mock_config, mock_database):
        """Test scrape cycle with multiple stockists."""
        stockist1 = Mock()
        stockist1.name = "stockist1.com"
        stockist1.messengers = []
        stockist1.get_amiibo.return_value = []

        stockist2 = Mock()
        stockist2.name = "stockist2.com"
        stockist2.messengers = []
        stockist2.get_amiibo.return_value = []

        stockists = Mock()
        stockists.all_stockists = [stockist1, stockist2]
        stockists.messengers = Mock()
        stockists.messengers.all_messengers = []

        scraper = Scraper(
            config=mock_config,
            stockists=stockists,
            database=mock_database,
        )

        scraper.scrape_cycle()

        # Should scrape both stockists
        assert mock_database.record_scraping_failure.call_count == 2
        assert mock_database.update_or_insert_last_scraped.call_count == 2

    def test_scrape_cycle_messenger_not_assigned(
        self, scraper, mock_stockist, mock_database
    ):
        """Test scrape cycle when messenger is not assigned to stockist."""
        items = [
            {
                "Title": "Test Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/1",
                "Website": "test.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            }
        ]
        mock_stockist.get_amiibo.return_value = items
        mock_stockist.messengers = ["different_messenger"]  # Not matching
        mock_database.check_then_add_or_update_amiibo.return_value = items

        scraper.scrape_cycle()

        # Messenger should not be called
        for messenger in scraper.messengers.all_messengers:
            messenger.send_embed_message.assert_not_called()

    def test_scrape_cycle_mixed_valid_invalid_data(
        self, scraper, mock_stockist, mock_database
    ):
        """Test scrape cycle with mix of valid and invalid data."""
        items = [
            {
                "Title": "Valid Amiibo",
                "Price": "$19.99",
                "Stock": "In stock",
                "URL": "https://test.com/1",
                "Website": "test.com",
                "Image": "https://test.com/img.jpg",
                "Colour": 0x00FF00,
            },
            {
                "Title": "Invalid Amiibo",
                # Missing required fields
            },
        ]
        mock_stockist.get_amiibo.return_value = items

        def validate_side_effect(item):
            if "Stock" not in item:
                raise ValueError("Invalid data")
            return True

        mock_database._validate_amiibo_data.side_effect = validate_side_effect
        mock_database.check_then_add_or_update_amiibo.return_value = []

        scraper.scrape_cycle()

        # Should call check_then_add with only valid item
        call_args = mock_database.check_then_add_or_update_amiibo.call_args
        assert len(call_args[0][0]) == 1
        assert call_args[0][0][0]["Title"] == "Valid Amiibo"

    @patch("time.sleep")
    def test_scrape_exponential_backoff(self, mock_sleep, scraper):
        """Test exponential backoff timing."""
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.Timeout("Timeout"),
            None,
        ]

        scraper.scrape()

        # Check backoff times: 2^1 = 2, 2^2 = 4
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 2
        assert calls[1][0][0] == 4
