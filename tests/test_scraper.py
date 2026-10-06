from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from result import DeliveryResult, DeliveryStatus, RunResult, RunStatus
from scraper import CycleStats, Scraper
from timeutil import utcnow


def _outbox_row(item, row_id=1, **overrides):
    row = SimpleNamespace(
        id=row_id,
        website=item["Website"],
        url=item["URL"],
        title=item["Title"],
        stock_status=item["Stock"],
        price=item["Price"],
        image=item["Image"],
        colour=item["Colour"],
        release_date=item.get("Release"),
        status="pending",
        attempts=0,
        created_at=utcnow(),
    )
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


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
        db.get_failure_alert_state.return_value = (0, None)
        db.get_last_healthy_count.return_value = 100
        db.record_scrape_attempt.return_value = None
        db.record_healthy_scrape.return_value = None
        db.record_unhealthy_scrape.return_value = 1
        db.get_consecutive_unhealthy_obs.return_value = 1
        db._validate_amiibo_data.return_value = True
        db.check_then_add_or_update_amiibo.return_value = []
        db.get_pending_outbox.return_value = []
        db.get_delivery_status.return_value = None
        db.record_delivery.return_value = None
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
        messenger.send_embed_message.return_value = DeliveryResult(
            status=DeliveryStatus.SUCCESS,
            messenger_name="test_messenger",
            http_status=200,
        )
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
    def test_scrape_stockist_with_retry(self, mock_sleep, scraper, mock_stockist):
        mock_stockist.get_amiibo.side_effect = [
            Exception("Fail1"),
            Exception("Fail2"),
            [
                {
                    "Title": "Test",
                    "Price": "$19.99",
                    "Stock": "In stock",
                    "URL": "https://test.com/1",
                    "Website": "test.com",
                    "Image": "https://test.com/img.jpg",
                    "Colour": 0x00FF00,
                }
            ],
        ]

        result = scraper._scrape_stockist(mock_stockist)

        assert len(result) == 1
        assert mock_stockist.get_amiibo.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    def test_scrape_stockist_max_retries(self, mock_sleep, scraper, mock_stockist):
        mock_stockist.get_amiibo.side_effect = RuntimeError("Always fails")

        with pytest.raises(RuntimeError, match="Always fails"):
            scraper._scrape_stockist(mock_stockist)

        assert mock_stockist.get_amiibo.call_count == 3

    @patch("time.sleep")
    def test_scrape_stockist_backoff(self, mock_sleep, scraper, mock_stockist):
        mock_stockist.get_amiibo.side_effect = [
            Exception("Fail1"),
            Exception("Fail2"),
            [
                {
                    "Title": "Test",
                    "Price": "$19.99",
                    "Stock": "In stock",
                    "URL": "https://test.com/1",
                    "Website": "test.com",
                    "Image": "https://test.com/img.jpg",
                    "Colour": 0x00FF00,
                }
            ],
        ]

        scraper._scrape_stockist(mock_stockist)

        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 2
        assert calls[1][0][0] == 4

    def test_scrape_handles_exception(self, scraper):
        scraper.scrape_cycle = Mock()
        scraper.scrape_cycle.side_effect = Exception("Unexpected")

        result = scraper.scrape()

        assert result.status == RunStatus.FAILURE
        assert result.exit_code == 3

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
        mock_database.get_pending_outbox.return_value = [_outbox_row(items[0])]

        result = scraper.scrape_cycle()

        mock_messenger.send_embed_message.assert_called_once()
        sent = mock_messenger.send_embed_message.call_args[0][0]
        assert sent["Title"] == "Test Amiibo"
        assert sent["Stock"] == "In stock"
        mock_database.record_delivery.assert_called_once()
        assert (
            mock_database.record_delivery.call_args[1]["idempotency_key"] == "outbox:1"
        )
        mock_database.complete_outbox.assert_called_once_with(1, "done")
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
        mock_database.get_pending_outbox.return_value = [_outbox_row(items[0])]

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


def _scrape_item(
    stock="In stock",
    price="$19.99",
    url="https://t.com/1",
    colour=None,
    release=None,
):
    if colour is None:
        colour = 0x00FF00 if stock == "In stock" else 0xFF0000
    item = {
        "Title": "Test Amiibo",
        "Price": price,
        "Stock": stock,
        "URL": url,
        "Website": "t.com",
        "Image": "https://t.com/img.jpg",
        "Colour": colour,
    }
    if release is not None:
        item["Release"] = release
    return item


def _result(status, http_status=None, name="m1"):
    return DeliveryResult(status=status, messenger_name=name, http_status=http_status)


OK = DeliveryStatus.SUCCESS
TRANSIENT = DeliveryStatus.TRANSIENT_FAILURE
PERMANENT = DeliveryStatus.PERMANENT_FAILURE


class TestScraperOutboxDelivery:
    """End-to-end scrape_cycle tests against a real SQLite database."""

    @pytest.fixture(autouse=True)
    def no_sleep(self):
        with patch("time.sleep") as mock_sleep:
            self.sleep = mock_sleep
            yield mock_sleep

    @pytest.fixture
    def database(self):
        import os
        import uuid

        from config.config import DatabaseConfig
        from database import Database

        config = DatabaseConfig(
            engine="sqlite", name=f"test_scraper_{uuid.uuid4().hex[:8]}"
        )
        db = Database(config)
        db.ensure_schema()
        yield db
        db.engine.dispose()
        if os.path.exists(f"{config.name}.db"):
            os.remove(f"{config.name}.db")

    @staticmethod
    def _messenger(name="m1", results=None):
        m = Mock()
        m.name = name
        m.send_embed_message.side_effect = None
        m.send_embed_message.return_value = _result(OK, 200, name)
        if results is not None:
            m.send_embed_message.side_effect = results
        return m

    @staticmethod
    def _build(database, messengers, items_holder):
        stockist = Mock()
        stockist.name = "t.com"
        stockist.messengers = [m.name for m in messengers]
        stockist.get_amiibo.side_effect = lambda: list(items_holder["items"])
        stockists = Mock()
        stockists.all_stockists = [stockist]
        stockists.messengers = Mock()
        stockists.messengers.all_messengers = messengers
        return Scraper(config=Mock(), stockists=stockists, database=database), stockist

    @staticmethod
    def _expire_cooldown(database):
        from database import AmiiboStock

        with database.Session() as session:
            for item in session.query(AmiiboStock).all():
                if item.last_notified_at:
                    item.last_notified_at = utcnow() - timedelta(hours=2)
            session.commit()

    @staticmethod
    def _rows(database):
        from database import NotificationOutbox

        with database.Session() as session:
            return (
                session.query(NotificationOutbox).order_by(NotificationOutbox.id).all()
            )

    @staticmethod
    def _sent_statuses(messenger):
        return [c[0][0]["Stock"] for c in messenger.send_embed_message.call_args_list]

    def test_release_is_in_flushed_item_only_when_set(self, database):
        m = self._messenger()
        holder = {
            "items": [
                _scrape_item(
                    "Pre-order",
                    colour=0xFFA500,
                    url="https://t.com/1",
                    release="12 Nov 2026",
                ),
                _scrape_item(url="https://t.com/2"),
            ]
        }
        scraper, _ = self._build(database, [m], holder)

        scraper.scrape_cycle()

        sent = {c[0][0]["URL"]: c[0][0] for c in m.send_embed_message.call_args_list}
        assert sent["https://t.com/1"]["Release"] == "12 Nov 2026"
        assert sent["https://t.com/1"]["Stock"] == "Pre-order"
        assert "Release" not in sent["https://t.com/2"]

    def test_new_item_is_delivered_and_row_done(self, database):
        m = self._messenger()
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m], holder)

        result = scraper.scrape_cycle()

        assert result.succeeded == 1
        assert result.notifications_sent == 1
        assert self._sent_statuses(m) == ["In stock"]
        rows = self._rows(database)
        assert [(r.status, r.attempts) for r in rows] == [("done", 1)]
        assert rows[0].completed_at is not None

    def test_restock_is_delivered(self, database):
        m = self._messenger()
        holder = {"items": [_scrape_item("Out of Stock")]}
        scraper, _ = self._build(database, [m], holder)
        scraper.scrape_cycle()

        holder["items"] = [_scrape_item("In stock")]
        result = scraper.scrape_cycle()

        assert result.notifications_sent == 1
        assert self._sent_statuses(m) == ["Out of Stock", "In stock"]
        sent = m.send_embed_message.call_args[0][0]
        assert sent["Colour"] == 0x00FF00
        assert sent["Price"] == "$19.99"
        assert sent["Website"] == "t.com"

    def test_restock_sellout_restock_delivers_each_transition(self, database):
        m = self._messenger()
        holder = {"items": [_scrape_item("Out of Stock")]}
        scraper, _ = self._build(database, [m], holder)
        scraper.scrape_cycle()
        for stock in ["In stock", "Out of Stock", "In stock"]:
            self._expire_cooldown(database)
            holder["items"] = [_scrape_item(stock)]
            scraper.scrape_cycle()

        assert self._sent_statuses(m) == [
            "Out of Stock",
            "In stock",
            "Out of Stock",
            "In stock",
        ]
        assert self._sent_statuses(m).count("In stock") == 2

    def test_two_price_changes_are_both_delivered(self, database):
        m = self._messenger()
        holder = {"items": [_scrape_item(price="$19.99")]}
        scraper, _ = self._build(database, [m], holder)
        scraper.scrape_cycle()
        for price in ["$24.99", "$29.99"]:
            self._expire_cooldown(database)
            holder["items"] = [_scrape_item(price=price)]
            scraper.scrape_cycle()

        sent = [c[0][0] for c in m.send_embed_message.call_args_list]
        assert [s["Stock"] for s in sent] == [
            "In stock",
            "Price change",
            "Price change",
        ]
        assert [s["Price"] for s in sent[1:]] == ["$24.99", "$29.99"]
        from database import NotificationDelivery

        with database.Session() as session:
            keys = {d.idempotency_key for d in session.query(NotificationDelivery)}
        assert len(keys) == 3

    def test_delisting_is_delivered_once(self, database):
        m = self._messenger()
        keep = _scrape_item(url="https://t.com/1")
        gone = _scrape_item(url="https://t.com/2")
        holder = {"items": [keep, gone]}
        scraper, _ = self._build(database, [m], holder)
        scraper.scrape_cycle()
        holder["items"] = [keep]
        for _ in range(6):
            scraper.scrape_cycle()

        assert self._sent_statuses(m).count("Delisted") == 1

    def test_transient_failure_stays_pending_and_is_retried_with_empty_scrape(
        self, database
    ):
        m = self._messenger(
            results=[
                _result(TRANSIENT, 429),
                _result(OK, 200),
            ]
        )
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m], holder)

        result = scraper.scrape_cycle()
        assert result.notifications_sent == 0
        row = self._rows(database)[0]
        assert (row.status, row.attempts) == ("pending", 1)

        # Next run the scrape returns nothing (counted as a failure) but the
        # pending notification must still be retried.
        holder["items"] = []
        result = scraper.scrape_cycle()
        assert result.failed == 1
        assert result.notifications_sent == 1
        assert m.send_embed_message.call_count == 2
        row = self._rows(database)[0]
        assert row.status == "done"
        assert row.attempts == 2

    def test_pending_is_retried_when_scrape_raises(self, database):
        m = self._messenger(results=[_result(TRANSIENT, 503), _result(OK, 200)])
        holder = {"items": [_scrape_item()]}
        scraper, stockist = self._build(database, [m], holder)
        scraper.scrape_cycle()

        stockist.get_amiibo.side_effect = Exception("boom")
        result = scraper.scrape_cycle()

        assert result.failed == 1
        assert result.notifications_sent == 1
        assert self._rows(database)[0].status == "done"

    def test_retry_does_not_resend_to_messenger_that_succeeded(self, database):
        m1 = self._messenger("m1")
        m2 = self._messenger(
            "m2", results=[_result(TRANSIENT, 500, "m2"), _result(OK, 200, "m2")]
        )
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m1, m2], holder)

        first = scraper.scrape_cycle()
        assert first.notifications_sent == 1
        assert self._rows(database)[0].status == "pending"

        second = scraper.scrape_cycle()
        assert second.notifications_sent == 1
        assert m1.send_embed_message.call_count == 1
        assert m2.send_embed_message.call_count == 2
        assert self._rows(database)[0].status == "done"

    def test_permanent_failure_is_final_and_not_retried(self, database):
        m1 = self._messenger("m1", results=[_result(PERMANENT, 404, "m1")])
        m2 = self._messenger(
            "m2", results=[_result(TRANSIENT, 500, "m2"), _result(OK, 200, "m2")]
        )
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m1, m2], holder)

        scraper.scrape_cycle()
        assert self._rows(database)[0].status == "pending"
        scraper.scrape_cycle()

        assert m1.send_embed_message.call_count == 1
        assert m2.send_embed_message.call_count == 2
        assert self._rows(database)[0].status == "done"

    def test_rate_limit_stops_sends_without_using_attempts(self, database):
        m = self._messenger(results=[_result(TRANSIENT, 429), _result(OK, 200)])
        holder = {
            "items": [_scrape_item(url=f"https://t.com/{i}") for i in range(1, 4)]
        }
        scraper, _ = self._build(database, [m], holder)

        result = scraper.scrape_cycle()

        assert result.notifications_sent == 0
        assert m.send_embed_message.call_count == 1
        rows = self._rows(database)
        assert [r.status for r in rows] == ["pending"] * 3
        assert [r.attempts for r in rows] == [1, 0, 0]

    def test_rate_limit_only_affects_the_limited_messenger(self, database):
        m1 = self._messenger("m1", results=[_result(TRANSIENT, 429, "m1")])
        m2 = self._messenger("m2")
        holder = {
            "items": [_scrape_item(url=f"https://t.com/{i}") for i in range(1, 3)]
        }
        scraper, _ = self._build(database, [m1, m2], holder)

        result = scraper.scrape_cycle()

        assert m1.send_embed_message.call_count == 1
        assert m2.send_embed_message.call_count == 2
        assert result.notifications_sent == 2

    def test_old_row_is_expired_not_sent(self, database):
        from database import NotificationOutbox

        m = self._messenger()
        holder = {"items": [_scrape_item()]}
        scraper, stockist = self._build(database, [m], holder)
        stockist.get_amiibo.side_effect = Exception("down")
        with database.Session() as session:
            session.add(
                NotificationOutbox(
                    website="t.com",
                    url="https://t.com/1",
                    title="Old",
                    stock_status="In stock",
                    price="$1",
                    image="i",
                    colour=1,
                    created_at=utcnow() - timedelta(hours=25),
                )
            )
            session.commit()

        result = scraper.scrape_cycle()

        assert result.notifications_sent == 0
        m.send_embed_message.assert_not_called()
        row = self._rows(database)[0]
        assert row.status == "expired"
        assert row.completed_at is not None

    def test_recent_row_is_delivered_not_expired(self, database):
        from database import NotificationOutbox

        m = self._messenger()
        holder = {"items": []}
        scraper, _ = self._build(database, [m], holder)
        with database.Session() as session:
            session.add(
                NotificationOutbox(
                    website="t.com",
                    url="https://t.com/1",
                    title="Fresh",
                    stock_status="In stock",
                    price="$1",
                    image="i",
                    colour=1,
                    created_at=utcnow() - timedelta(hours=1),
                )
            )
            session.commit()

        result = scraper.scrape_cycle()

        assert result.notifications_sent == 1
        m.send_embed_message.assert_called_once()
        assert self._rows(database)[0].status == "done"

    def test_row_at_max_attempts_is_expired_not_sent(self, database):
        from constants import OUTBOX_MAX_ATTEMPTS
        from database import NotificationOutbox

        m = self._messenger()
        holder = {"items": []}
        scraper, _ = self._build(database, [m], holder)
        with database.Session() as session:
            session.add(
                NotificationOutbox(
                    website="t.com",
                    url="https://t.com/1",
                    title="Stuck",
                    stock_status="In stock",
                    price="$1",
                    image="i",
                    colour=1,
                    attempts=OUTBOX_MAX_ATTEMPTS,
                )
            )
            session.commit()

        scraper.scrape_cycle()

        m.send_embed_message.assert_not_called()
        assert self._rows(database)[0].status == "expired"

    def test_row_expires_after_repeated_transient_failures(self, database):
        from constants import OUTBOX_MAX_ATTEMPTS

        m = self._messenger(results=lambda item: _result(TRANSIENT, 500))
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m], holder)

        for _ in range(OUTBOX_MAX_ATTEMPTS + 1):
            scraper.scrape_cycle()

        assert m.send_embed_message.call_count == OUTBOX_MAX_ATTEMPTS
        assert self._rows(database)[0].status == "expired"

    def test_sleeps_between_sends(self, database):
        from constants import MESSAGE_SEND_DELAY

        m = self._messenger()
        holder = {
            "items": [_scrape_item(url=f"https://t.com/{i}") for i in range(1, 4)]
        }
        scraper, _ = self._build(database, [m], holder)

        scraper.scrape_cycle()

        assert m.send_embed_message.call_count == 3
        assert [c[0][0] for c in self.sleep.call_args_list] == [MESSAGE_SEND_DELAY] * 2

    def test_only_assigned_messengers_receive(self, database):
        m1 = self._messenger("m1")
        m2 = self._messenger("m2")
        holder = {"items": [_scrape_item()]}
        scraper, stockist = self._build(database, [m1, m2], holder)
        stockist.messengers = ["m2"]

        scraper.scrape_cycle()

        m1.send_embed_message.assert_not_called()
        assert m2.send_embed_message.call_count == 1

    def test_flush_failure_does_not_break_cycle(self, database):
        m = self._messenger()
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m], holder)
        with patch.object(
            database, "get_pending_outbox", side_effect=RuntimeError("db down")
        ):
            result = scraper.scrape_cycle()
        assert result.succeeded == 1
        assert result.notifications_sent == 0

    def test_outbox_rows_are_per_website(self, database):
        m = self._messenger()
        other = _scrape_item()
        other["Website"] = "other.com"
        database.check_then_add_or_update_amiibo([other])
        holder = {"items": [_scrape_item()]}
        scraper, _ = self._build(database, [m], holder)

        scraper.scrape_cycle()

        assert m.send_embed_message.call_count == 1
        assert [r.status for r in self._rows(database) if r.website == "other.com"] == [
            "pending"
        ]


class TestStockistFailureAlerts:
    """Failure and recovery messages, against a real SQLite database."""

    @pytest.fixture(autouse=True)
    def no_sleep(self):
        with patch("time.sleep"):
            yield

    @pytest.fixture
    def database(self):
        import os
        import uuid

        from config.config import DatabaseConfig
        from database import Database

        config = DatabaseConfig(
            engine="sqlite", name=f"test_failures_{uuid.uuid4().hex[:8]}"
        )
        db = Database(config)
        db.ensure_schema()
        yield db
        db.engine.dispose()
        if os.path.exists(f"{config.name}.db"):
            os.remove(f"{config.name}.db")

    @staticmethod
    def _messenger(name="m1", status=OK):
        m = Mock()
        m.name = name
        m.send_message.return_value = _result(status, 200, name)
        m.send_embed_message.return_value = _result(OK, 200, name)
        return m

    @staticmethod
    def _build(database, messengers, holder, stockist_messengers=None):
        stockist = Mock()
        stockist.name = "Nintendo UK"
        stockist.messengers = stockist_messengers or [m.name for m in messengers]

        def get_amiibo():
            if holder["mode"] == "raise":
                raise RuntimeError("boom\nline two")
            if holder["mode"] == "empty":
                return []
            return [_scrape_item()]

        stockist.get_amiibo.side_effect = get_amiibo
        stockists = Mock()
        stockists.all_stockists = [stockist]
        stockists.messengers = Mock()
        stockists.messengers.all_messengers = messengers
        return Scraper(config=Mock(), stockists=stockists, database=database)

    @staticmethod
    def _run(scraper, times):
        for _ in range(times):
            scraper.scrape_cycle()

    def test_threshold_boundary_and_no_repeat(self, database):
        m = self._messenger()
        holder = {"mode": "raise"}
        scraper = self._build(database, [m], holder)

        self._run(scraper, 5)
        m.send_message.assert_not_called()

        self._run(scraper, 1)
        assert m.send_message.call_count == 1
        message = m.send_message.call_args[0][0]
        assert message.startswith("Amiibot: Nintendo UK has failed 6 runs in a row")
        assert "boom line two" in message
        assert "paused until it recovers" in message
        assert database.get_failure_alert_state("Nintendo UK")[1] is not None

        self._run(scraper, 1)
        assert m.send_message.call_count == 1

    def test_empty_result_uses_returned_no_items(self, database):
        m = self._messenger()
        scraper = self._build(database, [m], {"mode": "empty"})
        self._run(scraper, 6)
        assert "(last error: returned no items)" in m.send_message.call_args[0][0]

    def test_failed_send_retries_next_run(self, database):
        m = self._messenger(status=DeliveryStatus.TRANSIENT_FAILURE)
        scraper = self._build(database, [m], {"mode": "raise"})

        self._run(scraper, 6)
        assert m.send_message.call_count == 1
        assert database.get_failure_alert_state("Nintendo UK")[1] is None

        self._run(scraper, 1)
        assert m.send_message.call_count == 2

        m.send_message.return_value = _result(OK, 200, "m1")
        self._run(scraper, 1)
        assert m.send_message.call_count == 3
        assert database.get_failure_alert_state("Nintendo UK")[1] is not None

        self._run(scraper, 1)
        assert m.send_message.call_count == 3

    def test_inactive_messenger_leaves_alert_unsent(self, database):
        m = self._messenger(status=DeliveryStatus.INACTIVE)
        scraper = self._build(database, [m], {"mode": "raise"})
        self._run(scraper, 6)
        assert database.get_failure_alert_state("Nintendo UK")[1] is None

    def test_one_successful_messenger_is_enough(self, database):
        bad = self._messenger("bad", DeliveryStatus.PERMANENT_FAILURE)
        good = self._messenger("good")
        scraper = self._build(database, [bad, good], {"mode": "raise"})
        self._run(scraper, 6)
        bad.send_message.assert_called_once()
        good.send_message.assert_called_once()
        assert database.get_failure_alert_state("Nintendo UK")[1] is not None

    def test_only_stockist_messengers_receive_messages(self, database):
        mine = self._messenger("mine")
        other = self._messenger("other")
        scraper = self._build(
            database, [mine, other], {"mode": "raise"}, stockist_messengers=["mine"]
        )
        self._run(scraper, 6)
        mine.send_message.assert_called_once()
        other.send_message.assert_not_called()

    def test_recovery_sent_once_and_flag_cleared(self, database):
        m = self._messenger()
        holder = {"mode": "raise"}
        scraper = self._build(database, [m], holder)
        self._run(scraper, 7)
        assert m.send_message.call_count == 1

        holder["mode"] = "ok"
        self._run(scraper, 1)
        assert m.send_message.call_count == 2
        assert m.send_message.call_args[0][0] == (
            "Amiibot: Nintendo UK is working again after 7 failed runs."
        )
        assert database.get_failure_alert_state("Nintendo UK") == (0, None)

        self._run(scraper, 2)
        assert m.send_message.call_count == 2

    def test_no_recovery_message_if_no_alert_was_sent(self, database):
        m = self._messenger()
        holder = {"mode": "raise"}
        scraper = self._build(database, [m], holder)
        self._run(scraper, 5)
        holder["mode"] = "ok"
        self._run(scraper, 1)
        m.send_message.assert_not_called()

    def test_flag_cleared_even_if_recovery_send_fails(self, database):
        m = self._messenger()
        holder = {"mode": "raise"}
        scraper = self._build(database, [m], holder)
        self._run(scraper, 6)
        m.send_message.return_value = _result(DeliveryStatus.TRANSIENT_FAILURE, 500)
        holder["mode"] = "ok"
        self._run(scraper, 2)
        assert m.send_message.call_count == 2
        assert database.get_failure_alert_state("Nintendo UK") == (0, None)

    def test_new_streak_alerts_again_after_recovery(self, database):
        m = self._messenger()
        holder = {"mode": "raise"}
        scraper = self._build(database, [m], holder)
        self._run(scraper, 6)
        holder["mode"] = "ok"
        self._run(scraper, 1)
        holder["mode"] = "raise"
        self._run(scraper, 6)
        texts = [c[0][0] for c in m.send_message.call_args_list]
        assert len(texts) == 3
        assert "failed 6 runs" in texts[0]
        assert "working again" in texts[1]
        assert "failed 6 runs" in texts[2]

    def test_messenger_exception_cannot_break_cycle(self, database):
        m = self._messenger()
        m.send_message.side_effect = RuntimeError("discord exploded")
        scraper = self._build(database, [m], {"mode": "raise"})
        self._run(scraper, 5)
        result = scraper.scrape_cycle()
        assert result.failed == 1
        assert database.get_failure_alert_state("Nintendo UK")[1] is None

    def test_database_error_cannot_break_cycle(self, database):
        m = self._messenger()
        scraper = self._build(database, [m], {"mode": "raise"})
        with patch.object(
            database, "get_failure_alert_state", side_effect=RuntimeError("db down")
        ):
            result = scraper.scrape_cycle()
        assert result.failed == 1

    def test_long_error_is_truncated(self, database):
        m = self._messenger()
        holder = {"mode": "raise"}
        scraper = self._build(database, [m], holder)
        scraper.stockists.all_stockists[0].get_amiibo.side_effect = RuntimeError(
            "x" * 5000
        )
        self._run(scraper, 6)
        assert len(m.send_message.call_args[0][0]) < 400
