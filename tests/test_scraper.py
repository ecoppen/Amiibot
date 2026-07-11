import pytest
from unittest.mock import Mock, patch
import requests
from scraper import Scraper
from result import RunResult, RunStatus, FailureCategory
from scraper import CycleStats


class TestScraper:
    @pytest.fixture
    def mock_config(self):
        return Mock()

    @pytest.fixture
    def mock_database(self):
        db = Mock()
        db.record_scraping_failure.return_value = 1
        db.record_scraping_success.return_value = None
        db.get_consecutive_failures.return_value = 0
        db.get_last_healthy_count.return_value = 100
        db.record_scrape_attempt.return_value = None
        db.record_healthy_scrape.return_value = None
        db.record_unhealthy_scrape.return_value = 1
        db.get_consecutive_unhealthy_obs.return_value = 1
        db._validate_amiibo_data.return_value = True
        db.check_then_add_or_update_amiibo.return_value = []
        db.should_suppress_notification.return_value = False
        db.record_notification.return_value = None
        return db

    @pytest.fixture
    def mock_stockist(self):
        stockist = Mock()
        stockist.name = "test.com"
        stockist.messengers = ["test_messenger"]
        stockist.get_amiibo.return_value = []
        return stockist

    @pytest.fixture
    def mock_messenger(self):
        messenger = Mock()
        messenger.name = "test_messenger"
        messenger.send_embed_message.return_value = None
        return messenger

    @pytest.fixture
    def mock_stockists(self, mock_stockist, mock_messenger):
        stockists = Mock()
        stockists.all_stockists = [mock_stockist]
        messenger_manager = Mock()
        messenger_manager.all_messengers = [mock_messenger]
        stockists.messengers = messenger_manager
        return stockists

    @pytest.fixture
    def scraper(self, mock_config, mock_stockists, mock_database):
        return Scraper(
            config=mock_config,
            stockists=mock_stockists,
            database=mock_database,
        )

    def test_scraper_initialization(
        self, scraper, mock_config, mock_stockists, mock_database
    ):
        assert scraper.config == mock_config
        assert scraper.stockists == mock_stockists
        assert scraper.database == mock_database
        assert scraper.messengers == mock_stockists.messengers

    def test_scrape_returns_run_result(self, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.return_value = CycleStats(
            succeeded=1, failed=0, notifications_sent=5
        )
        result = scraper.scrape()
        assert isinstance(result, RunResult)
        assert result.status == RunStatus.SUCCESS
        assert result.exit_code == 0
        assert result.stockists_attempted == 1
        assert result.stockists_succeeded == 1
        assert result.stockists_failed == 0
        assert result.notifications_sent == 5

    def test_scrape_returns_partial_on_some_failures(self, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.return_value = CycleStats(
            succeeded=1, failed=1, notifications_sent=3
        )
        result = scraper.scrape()
        assert result.status == RunStatus.PARTIAL
        assert result.exit_code == 2
        assert result.stockists_succeeded == 1
        assert result.stockists_failed == 1

    @patch("time.sleep")
    def test_scrape_timeout_with_retry_returns_result(self, mock_sleep, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            CycleStats(succeeded=1, failed=0, notifications_sent=0),
        ]
        result = scraper.scrape()
        assert scraper.scrape_cycle.call_count == 2
        assert result.status == RunStatus.SUCCESS
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_scrape_max_retries_returns_failure(self, mock_sleep, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = requests.exceptions.Timeout("Timeout")
        result = scraper.scrape()
        assert scraper.scrape_cycle.call_count == 3
        assert result.status == RunStatus.FAILURE
        assert result.exit_code == 3
        assert result.failure_category == FailureCategory.NETWORK
        assert len(result.errors) > 0

    @patch("time.sleep")
    def test_scrape_too_many_redirects_returns_failure(self, mock_sleep, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = requests.exceptions.TooManyRedirects(
            "Redirects"
        )
        result = scraper.scrape()
        assert scraper.scrape_cycle.call_count == 1
        assert result.status == RunStatus.FAILURE
        assert result.exit_code == 3
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_scrape_unexpected_error_returns_failure(self, mock_sleep, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = ValueError("Unexpected error")
        result = scraper.scrape()
        assert scraper.scrape_cycle.call_count == 1
        assert result.status == RunStatus.FAILURE
        assert result.exit_code == 3
        mock_sleep.assert_not_called()

    def test_scrape_cycle_empty_stockists(self, mock_config, mock_database):
        empty_stockists = Mock()
        empty_stockists.all_stockists = []
        empty_stockists.messengers = Mock()
        empty_stockists.messengers.all_messengers = []
        scraper = Scraper(
            config=mock_config, stockists=empty_stockists, database=mock_database
        )
        result = scraper.scrape_cycle()
        assert isinstance(result, CycleStats)
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.notifications_sent == 0

    def test_scrape_cycle_stockist_exception(
        self, scraper, mock_stockist, mock_database
    ):
        mock_stockist.get_amiibo.side_effect = Exception("Scraping error")
        result = scraper.scrape_cycle()
        assert result.failed == 1
        mock_database.record_scraping_failure.assert_called_once_with("test.com")
        mock_database.record_scrape_attempt.assert_called_once()

    def test_scrape_cycle_empty_items_tracks_failure(self, scraper, mock_database):
        result = scraper.scrape_cycle()
        assert result.failed == 1
        mock_database.record_scraping_failure.assert_called_once()
        mock_database.record_scrape_attempt.assert_called_once()

    def test_scrape_cycle_success_with_items(
        self, scraper, mock_stockist, mock_database
    ):
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
        mock_database.get_last_healthy_count.return_value = 2

        result = scraper.scrape_cycle()

        assert result.succeeded == 1
        assert result.failed == 0
        mock_database.record_scraping_success.assert_called_once_with("test.com")
        mock_database.record_healthy_scrape.assert_called_once()

    def test_scrape_cycle_with_all_invalid_data_is_failure(
        self, scraper, mock_stockist, mock_database
    ):
        items = [
            {
                "Title": "Invalid Amiibo",
                "Price": "$19.99",
            }
        ]
        mock_stockist.get_amiibo.return_value = items
        mock_database._validate_amiibo_data.side_effect = ValueError("Invalid data")

        result = scraper.scrape_cycle()

        assert result.failed == 1
        assert result.succeeded == 0
        mock_database.record_scraping_failure.assert_called_once()
        mock_database.record_scraping_success.assert_not_called()
        mock_database.check_then_add_or_update_amiibo.assert_not_called()

    def test_scrape_cycle_with_notifications(
        self, scraper, mock_stockist, mock_database, mock_messenger
    ):
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

        result = scraper.scrape_cycle()

        mock_messenger.send_embed_message.assert_called_once()
        assert result.notifications_sent == 1

    def test_scrape_cycle_multiple_stockists(self, mock_config, mock_database):
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
            config=mock_config, stockists=stockists, database=mock_database
        )
        result = scraper.scrape_cycle()
        assert result.failed == 2
        assert result.succeeded == 0

    def test_scrape_cycle_messenger_not_assigned(
        self, scraper, mock_stockist, mock_database
    ):
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
        mock_stockist.messengers = ["different_messenger"]
        mock_database.check_then_add_or_update_amiibo.return_value = items

        result = scraper.scrape_cycle()

        assert result.succeeded == 1
        assert result.notifications_sent == 0

    def test_scrape_cycle_mixed_valid_invalid_data(
        self, scraper, mock_stockist, mock_database
    ):
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
            {"Title": "Invalid Amiibo"},
        ]
        mock_stockist.get_amiibo.return_value = items

        def validate_side_effect(item):
            if "Stock" not in item:
                raise ValueError("Invalid data")
            return True

        mock_database._validate_amiibo_data.side_effect = validate_side_effect

        result = scraper.scrape_cycle()

        call_args = mock_database.check_then_add_or_update_amiibo.call_args
        assert len(call_args[0][0]) == 1
        assert call_args[0][0][0]["Title"] == "Valid Amiibo"
        assert result.succeeded == 1

    @patch("time.sleep")
    def test_scrape_exponential_backoff_returns_result(self, mock_sleep, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            requests.exceptions.Timeout("Timeout"),
            CycleStats(succeeded=1, failed=0, notifications_sent=0),
        ]
        result = scraper.scrape()
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 2
        assert calls[1][0][0] == 4
        assert result.status == RunStatus.SUCCESS

    def test_scrape_cycle_with_suppressed_notifications(
        self, scraper, mock_stockist, mock_database, mock_messenger
    ):
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
        mock_database.should_suppress_notification.return_value = True

        result = scraper.scrape_cycle()

        mock_messenger.send_embed_message.assert_not_called()
        assert result.notifications_sent == 0

    def test_low_ratio_skips_delisting_below_threshold(
        self, scraper, mock_stockist, mock_database
    ):
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
        mock_database.get_last_healthy_count.return_value = 100
        mock_database.record_unhealthy_scrape.return_value = 1
        mock_database.get_consecutive_unhealthy_obs.return_value = 1

        scraper.scrape_cycle()

        call_args = mock_database.check_then_add_or_update_amiibo.call_args
        assert call_args[1]["skip_delisting"] is True

    def test_low_ratio_accepts_baseline_after_threshold(
        self, scraper, mock_stockist, mock_database
    ):
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
        mock_database.get_last_healthy_count.return_value = 100
        mock_database.record_unhealthy_scrape.return_value = 2
        mock_database.get_consecutive_unhealthy_obs.return_value = 2

        scraper.scrape_cycle()

        mock_database.record_healthy_scrape.assert_called_once_with("test.com", 1)
        call_args = mock_database.check_then_add_or_update_amiibo.call_args
        assert call_args[1]["skip_delisting"] is False

    def test_healthy_ratio_updates_baseline(
        self, scraper, mock_stockist, mock_database
    ):
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
        mock_database.get_last_healthy_count.return_value = 1

        scraper.scrape_cycle()

        mock_database.record_healthy_scrape.assert_called_once_with("test.com", 1)

    def test_no_prior_baseline_records_healthy(
        self, scraper, mock_stockist, mock_database
    ):
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
        mock_database.get_last_healthy_count.return_value = 0

        scraper.scrape_cycle()

        mock_database.record_healthy_scrape.assert_called_once_with("test.com", 1)
