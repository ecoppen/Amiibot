"""
Unit tests for stockist module.
"""

from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
import requests
from selenium.common.exceptions import WebDriverException

from constants import REQUEST_TIMEOUT
from stockist.bestbuy import Bestbuy
from stockist.bestbuyca import BestbuyCA
from stockist.cexuk import CexUK
from stockist.gamestop import Gamestop
from stockist.manager import STOCKIST_FACTORY, StockistManager
from stockist.nintendouk import NintendoUK
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto
from stockist.stockist import Stock, Stockist
from stockist.utils import send_public_request


def _uk_today() -> date:
    """Today in the UK, which is what the Nintendo UK parser compares against."""
    return datetime.now(ZoneInfo("Europe/London")).date()


class TestStock:
    """Test Stock enumeration."""

    def test_stock_enum_values(self):
        """Test Stock enum has correct values."""
        assert Stock.DELISTED.value == "Delisted"
        assert Stock.IN_STOCK.value == "In stock"
        assert Stock.OUT_OF_STOCK.value == "Out of Stock"
        assert Stock.PRICE_CHANGE.value == "Price change"
        assert Stock.PRE_ORDER.value == "Pre-order"

    def test_stock_enum_members(self):
        """Test Stock enum has all expected members."""
        expected_members = [
            "DELISTED",
            "IN_STOCK",
            "OUT_OF_STOCK",
            "PRICE_CHANGE",
            "PRE_ORDER",
        ]
        actual_members = [member.name for member in Stock]
        assert set(expected_members) == set(actual_members)


class TestStockist:
    """Test base Stockist class."""

    @pytest.fixture
    def stockist(self):
        """Create test stockist instance."""
        return Stockist(messengers=["test_messenger"])

    def test_stockist_initialization(self, stockist):
        """Test stockist initializes correctly."""
        assert stockist.messengers == ["test_messenger"]
        assert stockist.params == {}
        assert stockist.base_url is None
        assert stockist.name is None

    @patch("stockist.stockist.send_public_request")
    def test_scrape(self, mock_request, stockist):
        """Test scrape method calls send_public_request."""
        mock_response = Mock()
        mock_request.return_value = mock_response

        result = stockist.scrape(url="https://test.com", payload={"key": "value"})

        assert result == mock_response
        mock_request.assert_called_once_with(
            url="https://test.com",
            payload={"key": "value"},
            timeout=REQUEST_TIMEOUT,
        )

    @patch("stockist.stockist.send_public_request")
    def test_scrape_uses_the_stockist_timeout(self, mock_request, stockist):
        stockist.request_timeout = 30

        stockist.scrape(url="https://test.com", payload=None)

        assert mock_request.call_args.kwargs["timeout"] == 30

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_scrape_with_selenium_success(self, mock_wait, mock_chrome, stockist):
        """Test selenium scraping returns page source."""
        mock_driver = Mock()
        mock_driver.page_source = "<html>test</html>"
        mock_chrome.return_value = mock_driver

        result = stockist.scrape_with_selenium(url="https://test.com", payload=None)

        assert result == "<html>test</html>"
        mock_driver.quit.assert_called_once()

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_scrape_with_selenium_timeout(self, mock_wait, mock_chrome, stockist):
        """Test selenium timeout returns empty string."""
        from selenium.common.exceptions import TimeoutException

        mock_wait.return_value.until.side_effect = TimeoutException("timed out")
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver

        result = stockist.scrape_with_selenium(url="https://test.com", payload=None)

        assert result == ""

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_scrape_with_selenium_webdriver_exception(
        self, mock_wait, mock_chrome, stockist
    ):
        """Test WebDriverException returns empty string."""
        mock_wait.return_value.until.side_effect = WebDriverException("no driver")
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver

        result = stockist.scrape_with_selenium(url="https://test.com", payload=None)

        assert result == ""

    @pytest.mark.parametrize(
        "error",
        [WebDriverException("quit failed"), OSError("quit failed")],
    )
    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_scrape_with_selenium_quit_error(
        self, mock_wait, mock_chrome, stockist, error
    ):
        """Test quit errors are caught."""
        mock_driver = Mock()
        mock_driver.page_source = "<html>test</html>"
        mock_driver.quit.side_effect = error
        mock_chrome.return_value = mock_driver

        result = stockist.scrape_with_selenium(url="https://test.com", payload=None)

        assert result == "<html>test</html>"


class TestScrapeWithSeleniumPayload:
    @pytest.fixture
    def stockist(self):
        return Stockist(messengers=["test_messenger"])

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_payload_is_appended_to_the_url(self, mock_wait, mock_chrome, stockist):
        mock_driver = Mock()
        mock_driver.page_source = "<html></html>"
        mock_chrome.return_value = mock_driver

        stockist.scrape_with_selenium(
            url="https://test.com/list", payload={"start": 0, "sz": 300}
        )

        mock_driver.get.assert_called_once_with("https://test.com/list?start=0&sz=300")

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_payload_joins_an_existing_query_string(
        self, mock_wait, mock_chrome, stockist
    ):
        mock_driver = Mock()
        mock_driver.page_source = "<html></html>"
        mock_chrome.return_value = mock_driver

        stockist.scrape_with_selenium(url="https://test.com/?q=a", payload={"p": 2})

        mock_driver.get.assert_called_once_with("https://test.com/?q=a&p=2")

    @pytest.mark.parametrize("payload", [None, {}])
    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_no_payload_leaves_the_url_alone(
        self, mock_wait, mock_chrome, stockist, payload
    ):
        mock_driver = Mock()
        mock_driver.page_source = "<html></html>"
        mock_chrome.return_value = mock_driver

        stockist.scrape_with_selenium(url="https://test.com/#frag", payload=payload)

        mock_driver.get.assert_called_once_with("https://test.com/#frag")

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_wait_for_selector_waits_a_second_time(
        self, mock_wait, mock_chrome, stockist
    ):
        mock_driver = Mock()
        mock_driver.page_source = "<html>ready</html>"
        mock_chrome.return_value = mock_driver

        result = stockist.scrape_with_selenium(
            url="https://test.com", payload=None, wait_for=".item"
        )

        assert result == "<html>ready</html>"
        # Once for the page load, once for the selector.
        assert mock_wait.return_value.until.call_count == 2

    @patch("stockist.stockist.webdriver.Chrome")
    @patch("stockist.stockist.WebDriverWait")
    def test_wait_for_selector_timeout_still_returns_page(
        self, mock_wait, mock_chrome, stockist, caplog
    ):
        from selenium.common.exceptions import TimeoutException

        mock_wait.return_value.until.side_effect = [None, TimeoutException("late")]
        mock_driver = Mock()
        mock_driver.page_source = "<html>partial</html>"
        mock_chrome.return_value = mock_driver

        with caplog.at_level("WARNING", logger="stockist.stockist"):
            result = stockist.scrape_with_selenium(
                url="https://test.com", payload=None, wait_for=".item"
            )

        assert result == "<html>partial</html>"
        assert "Timed out waiting for '.item'" in caplog.text
        mock_driver.quit.assert_called_once()


class TestStockistUtils:
    @patch("stockist.utils._get_session")
    def test_send_public_request_success(self, mock_session_fn):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Success"
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_fn.return_value = mock_session

        result = send_public_request(url="https://test.com", payload={"key": "value"})

        assert result == mock_response
        mock_session.get.assert_called_once()

    @patch("stockist.utils._get_session")
    def test_send_public_request_timeout(self, mock_session_fn):
        from stockist.utils import BlankResponse

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.Timeout
        mock_session_fn.return_value = mock_session

        result = send_public_request(url="https://test.com", payload=None)

        assert isinstance(result, BlankResponse)

    @patch("stockist.utils._get_session")
    def test_send_public_request_connection_error(self, mock_session_fn):
        from stockist.utils import BlankResponse

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError
        mock_session_fn.return_value = mock_session

        result = send_public_request(url="https://test.com", payload=None)

        assert isinstance(result, BlankResponse)

    @patch("stockist.utils._get_session")
    def test_send_public_request_http_error(self, mock_session_fn):
        from stockist.utils import BlankResponse

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.HTTPError
        mock_session_fn.return_value = mock_session

        result = send_public_request(url="https://test.com", payload=None)

        assert isinstance(result, BlankResponse)

    @patch("stockist.utils._get_session")
    def test_send_public_request_too_many_redirects(self, mock_session_fn):
        from stockist.utils import BlankResponse

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.TooManyRedirects
        mock_session_fn.return_value = mock_session

        result = send_public_request(url="https://test.com", payload=None)

        assert isinstance(result, BlankResponse)

    @patch("stockist.utils._get_session")
    def test_send_public_request_generic_request_exception(self, mock_session_fn):
        from stockist.utils import BlankResponse

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.RequestException
        mock_session_fn.return_value = mock_session

        result = send_public_request(url="https://test.com", payload=None)

        assert isinstance(result, BlankResponse)

    @patch("stockist.utils._get_session")
    def test_send_public_request_appends_query_string(self, mock_session_fn):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Success"
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_fn.return_value = mock_session

        send_public_request(url="https://test.com", payload={"q": "amiibo", "p": 1})

        called_url = mock_session.get.call_args.kwargs["url"]
        assert called_url == "https://test.com?q=amiibo&p=1"

    @patch("stockist.utils._get_session")
    def test_send_public_request_no_payload_no_query(self, mock_session_fn):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Success"
        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_fn.return_value = mock_session

        send_public_request(url="https://test.com", payload=None)

        called_url = mock_session.get.call_args.kwargs["url"]
        assert called_url == "https://test.com"


class TestBuildUrl:
    def test_appends_with_question_mark(self):
        from stockist.utils import build_url

        assert build_url("https://t.com/p", {"a": 1, "b": "x y"}) == (
            "https://t.com/p?a=1&b=x+y"
        )

    def test_appends_with_ampersand_when_query_exists(self):
        from stockist.utils import build_url

        assert build_url("https://t.com/p?q=1", {"a": 1}) == "https://t.com/p?q=1&a=1"

    @pytest.mark.parametrize("payload", [None, {}])
    def test_no_payload_returns_url_unchanged(self, payload):
        from stockist.utils import build_url

        assert build_url("https://t.com/p#x", payload) == "https://t.com/p#x"


class TestBlankResponse:
    def test_content_is_empty_bytes(self):
        from stockist.utils import BlankResponse

        assert BlankResponse().content == b""
        assert isinstance(BlankResponse().content, bytes)
        # Parsers call .decode() on it, which must work.
        assert BlankResponse().content.decode("utf-8") == ""

    @patch("stockist.utils._get_session")
    def test_failed_request_gives_empty_bytes(self, mock_session_fn):
        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.Timeout
        mock_session_fn.return_value = mock_session

        assert send_public_request(url="https://test.com").content == b""


class TestEmptyResponseHandling:
    """Parsers report a failed request clearly instead of a decode error."""

    @pytest.mark.parametrize(
        "stockist_class,logger_name",
        [
            (NintendoUK, "stockist.nintendouk"),
            (BestbuyCA, "stockist.bestbuyca"),
            (CexUK, "stockist.cexuk"),
        ],
    )
    def test_blank_response_logs_clear_error(self, stockist_class, logger_name, caplog):
        from stockist.utils import BlankResponse

        stockist = stockist_class(messengers=["test"])
        with (
            patch.object(stockist_class, "scrape", return_value=BlankResponse()),
            caplog.at_level("ERROR", logger=logger_name),
        ):
            result = stockist.get_amiibo()

        assert result == []
        assert "request failed or returned nothing" in caplog.text
        assert "decode" not in caplog.text
        assert "Invalid JSON" not in caplog.text


class TestStockistManager:
    """Test StockistManager class."""

    @pytest.fixture
    def mock_messenger(self):
        """Create mock messenger."""
        messenger = Mock()
        messenger.name = "test_messenger"
        messenger.stockists = ["bestbuy.com"]
        return messenger

    @pytest.fixture
    def mock_messengers(self, mock_messenger):
        """Create mock messengers object."""
        messengers = Mock()
        messengers.all_messengers = [mock_messenger]
        return messengers

    def test_stockist_manager_initialization(self, mock_messengers):
        """Test StockistManager initializes correctly."""
        manager = StockistManager(messengers=mock_messengers)

        assert len(manager.all_stockists) == 1
        assert isinstance(manager.all_stockists[0], Bestbuy)
        assert "bestbuy.com" in manager.relationships

    def test_stockist_manager_multiple_stockists(self):
        """Test StockistManager with multiple stockists."""
        messenger1 = Mock()
        messenger1.name = "messenger1"
        messenger1.stockists = ["bestbuy.com", "gamestop.com"]

        messenger2 = Mock()
        messenger2.name = "messenger2"
        messenger2.stockists = ["nintendo.co.uk"]

        messengers = Mock()
        messengers.all_messengers = [messenger1, messenger2]

        manager = StockistManager(messengers=messengers)

        assert len(manager.all_stockists) == 3
        assert "bestbuy.com" in manager.relationships
        assert "gamestop.com" in manager.relationships
        assert "nintendo.co.uk" in manager.relationships

    def test_stockist_manager_unknown_stockist(self):
        """Test StockistManager handles unknown stockist."""
        messenger = Mock()
        messenger.name = "test_messenger"
        messenger.stockists = ["unknown-site.com"]

        messengers = Mock()
        messengers.all_messengers = [messenger]

        manager = StockistManager(messengers=messengers)

        # Should skip unknown stockist
        assert len(manager.all_stockists) == 0

    def test_stockist_manager_no_messengers(self):
        """Test StockistManager with no messengers."""
        messengers = Mock()
        messengers.all_messengers = []

        manager = StockistManager(messengers=messengers)

        assert len(manager.all_stockists) == 0
        assert manager._validate_stockists() is False

    def test_stockist_factory_completeness(self):
        """Test that STOCKIST_FACTORY has all expected stockists."""
        expected_stockists = [
            "bestbuy.com",
            "bestbuy.ca",
            "gamestop.com",
            "nintendo.co.uk",
            "play-asia.com",
            "shopto.net",
            "uk.webuy.com",
        ]

        for stockist in expected_stockists:
            assert stockist in STOCKIST_FACTORY

    @pytest.mark.parametrize(
        "removed", ["game.co.uk", "meccha-japan.com", "thesource.ca"]
    )
    def test_removed_stockists_are_not_in_factory(self, removed):
        assert removed not in STOCKIST_FACTORY

    def test_factory_matches_config_enum_apart_from_removed(self):
        from config.config import REMOVED_STOCKISTS
        from config.config import Stockist as ConfigStockist

        configurable = {s.value for s in ConfigStockist} - REMOVED_STOCKISTS
        assert configurable == set(STOCKIST_FACTORY)

    def test_validate_stockists_success(self, mock_messengers):
        """Test _validate_stockists returns True when stockists exist."""
        manager = StockistManager(messengers=mock_messengers)
        result = manager._validate_stockists()

        assert result is True

    def test_validate_stockists_failure(self):
        """Test _validate_stockists returns False when no stockists."""
        messengers = Mock()
        messengers.all_messengers = []

        manager = StockistManager(messengers=messengers)
        result = manager._validate_stockists()

        assert result is False


# Parametrized tests for all stockist implementations
@pytest.mark.parametrize(
    "stockist_class,expected_name,expected_base_url",
    [
        (
            Bestbuy,
            "Bestbuy US",
            "https://www.bestbuy.com/site/toys-to-life/amiibo/pcmcat385200050004.c?intl=nosplash",
        ),
        (BestbuyCA, "Bestbuy CA", "https://www.bestbuy.ca/api/v2/json/search"),
        (
            Gamestop,
            "Gamestop US",
            "https://www.gamestop.com/consoles-hardware/nintendo-switch/nintendo-switch-amiibo",
        ),
        (
            NintendoUK,
            "Nintendo UK",
            "https://store.nintendo.co.uk/api/catalog/products",
        ),
        (
            PlayAsia,
            "Playasia",
            "https://www.play-asia.com/games/amiibos/14/712od",
        ),
        (Shopto, "Shopto", "https://www.shopto.net/en/search/?input_search=amiibo"),
        (CexUK, "CeX UK", "https://wss2.cex.uk.webuy.io/v3/boxes"),
    ],
)
class TestStockistImplementations:
    """Test all stockist implementations."""

    def test_stockist_initialization(
        self, stockist_class, expected_name, expected_base_url
    ):
        """Test stockist initializes with correct attributes."""
        stockist = stockist_class(messengers=["test_messenger"])

        assert stockist.name == expected_name
        assert stockist.base_url == expected_base_url
        assert stockist.messengers == ["test_messenger"]
        assert hasattr(stockist, "params")

    def test_stockist_has_get_amiibo_method(
        self, stockist_class, expected_name, expected_base_url
    ):
        """Test stockist has get_amiibo method."""
        stockist = stockist_class(messengers=["test_messenger"])

        assert hasattr(stockist, "get_amiibo")
        assert callable(stockist.get_amiibo)

    def test_stockist_inherits_from_base(
        self, stockist_class, expected_name, expected_base_url
    ):
        """Test stockist inherits from Stockist base class."""
        stockist = stockist_class(messengers=["test_messenger"])

        assert isinstance(stockist, Stockist)

    @patch("stockist.stockist.send_public_request")
    def test_stockist_scrape_method_accessible(
        self, mock_request, stockist_class, expected_name, expected_base_url
    ):
        """Test stockist can use inherited scrape method."""
        mock_response = Mock()
        mock_response.content = b"Test content"
        mock_request.return_value = mock_response

        stockist = stockist_class(messengers=["test_messenger"])
        result = stockist.scrape(url="https://test.com", payload=None)

        assert result == mock_response


class TestBestbuySpecific:
    """Test Bestbuy-specific functionality."""

    @pytest.fixture
    def bestbuy(self):
        """Create Bestbuy instance."""
        return Bestbuy(messengers=["test_messenger"])

    def test_bestbuy_params_none(self, bestbuy):
        """Test Bestbuy params is None."""
        assert bestbuy.params is None

    @patch("stockist.bestbuy.Bestbuy.scrape")
    def test_bestbuy_get_amiibo_with_cards(self, mock_scrape, bestbuy):
        """Test Bestbuy get_amiibo with valid HTML."""
        mock_response = Mock()
        mock_response.content = b"""
        <html>
            <li class="sku-item">
                <h4 class="sku-title"><a href="/test">Test Amiibo</a></h4>
                <button class="c-button">Add to Cart</button>
                <div class="priceView-hero-price"><span>$19.99</span></div>
                <img class="product-image" src="https://test.com/image.jpg" />
            </li>
        </html>
        """
        mock_scrape.return_value = mock_response

        result = bestbuy.get_amiibo()

        assert isinstance(result, list)

    @patch("stockist.bestbuy.Bestbuy.scrape")
    def test_bestbuy_get_amiibo_empty_page(self, mock_scrape, bestbuy):
        """Test Bestbuy get_amiibo with empty HTML."""
        mock_response = Mock()
        mock_response.content = b"<html></html>"
        mock_scrape.return_value = mock_response

        result = bestbuy.get_amiibo()

        assert isinstance(result, list)


class TestNintendoUKSpecific:
    """Test Nintendo UK-specific functionality."""

    @pytest.fixture
    def nintendo_uk(self):
        """Create Nintendo UK instance."""
        return NintendoUK(messengers=["test_messenger"])

    def test_nintendo_uk_params(self, nintendo_uk):
        """Test Nintendo UK has correct params."""
        assert nintendo_uk.params["checkAvailability"] == "true"
        assert nintendo_uk.params["limit"] == 24
        assert nintendo_uk.params["sort"] == "newest-products"
        assert nintendo_uk.params["offset"] == 0

    @patch("stockist.nintendouk.NintendoUK.scrape")
    def test_nintendo_uk_get_amiibo_with_data(self, mock_scrape, nintendo_uk):
        """Test Nintendo UK get_amiibo with valid JSON."""
        mock_response = Mock()
        mock_response.content = b"""
        {
            "data": {
                "products": [
                    {
                        "name": "Test Amiibo",
                        "pricePerUnit": 19.99,
                        "c_productImages": ["test_image"],
                        "path": "/test-amiibo",
                        "c_availabilityModel": {"type": "InStock"}
                    }
                ]
            }
        }
        """
        mock_scrape.return_value = mock_response

        result = nintendo_uk.get_amiibo()

        assert isinstance(result, list)
        assert len(result) > 0

    @patch("stockist.nintendouk.NintendoUK.scrape")
    def test_nintendo_uk_get_amiibo_invalid_json(self, mock_scrape, nintendo_uk):
        """Test Nintendo UK handles invalid JSON."""
        mock_response = Mock()
        mock_response.content = b"Invalid JSON"
        mock_scrape.return_value = mock_response

        result = nintendo_uk.get_amiibo()

        assert isinstance(result, list)

    @patch("stockist.nintendouk.NintendoUK.scrape")
    def test_nintendo_uk_get_amiibo_no_data(self, mock_scrape, nintendo_uk):
        """Test Nintendo UK handles missing data."""
        mock_response = Mock()
        mock_response.content = b'{"data": null}'
        mock_scrape.return_value = mock_response

        result = nintendo_uk.get_amiibo()

        assert isinstance(result, list)

    @patch("stockist.nintendouk.NintendoUK.scrape")
    def test_nintendo_uk_get_amiibo_out_of_stock(self, mock_scrape, nintendo_uk):
        """Test Nintendo UK handles out of stock items."""
        mock_response = Mock()
        mock_response.content = b"""
        {
            "data": {
                "products": [
                    {
                        "name": "Test Amiibo",
                        "pricePerUnit": 19.99,
                        "c_productImages": ["test_image"],
                        "path": "/test-amiibo",
                        "c_availabilityModel": {"type": "OutOfStock"}
                    }
                ]
            }
        }
        """
        mock_scrape.return_value = mock_response

        result = nintendo_uk.get_amiibo()

        assert isinstance(result, list)
        if len(result) > 0:
            assert result[0]["Stock"] == Stock.OUT_OF_STOCK.value


class TestNintendoUKAvailability:
    """Availability mapping and release dates for Nintendo UK."""

    @staticmethod
    def _scrape(products):
        import json

        mock_response = Mock()
        mock_response.content = json.dumps({"data": {"products": products}}).encode()
        empty = Mock()
        empty.content = b'{"data": {"products": []}}'
        nintendo = NintendoUK(messengers=["m"])
        with patch.object(NintendoUK, "scrape", side_effect=[mock_response, empty]):
            return nintendo.get_amiibo()

    @staticmethod
    def _product(availability="InStock", **extra):
        product = {
            "name": "Test Amiibo",
            "pricePerUnit": 19.99,
            "c_productImages": ["test_image"],
            "path": "/test-amiibo",
            "c_availabilityModel": {"type": availability},
        }
        product.update(extra)
        return product

    @pytest.mark.parametrize(
        "api_type, stock, colour",
        [
            ("InStock", Stock.IN_STOCK, 0x00FF00),
            ("PreOrder", Stock.PRE_ORDER, 0xFFA500),
            ("OutOfStock", Stock.OUT_OF_STOCK, 0xFF0000),
        ],
    )
    def test_known_availability_types(self, api_type, stock, colour):
        result = self._scrape([self._product(api_type)])
        assert result[0]["Stock"] == stock.value
        assert result[0]["Colour"] == colour

    def test_unknown_type_is_out_of_stock_and_warns(self, caplog):
        with caplog.at_level("WARNING", logger="stockist.nintendouk"):
            result = self._scrape([self._product("BackOrder")])
        assert result[0]["Stock"] == Stock.OUT_OF_STOCK.value
        assert result[0]["Colour"] == 0xFF0000
        warnings = [r for r in caplog.records if "BackOrder" in r.getMessage()]
        assert len(warnings) == 1

    def test_future_release_date_is_formatted(self):
        future = _uk_today() + timedelta(days=30)
        result = self._scrape(
            [self._product("PreOrder", c_releaseDate=future.isoformat())]
        )
        assert result[0]["Release"] == f"{future.day} {future.strftime('%b %Y')}"

    def test_release_date_format_example(self):
        with patch("stockist.nintendouk.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2026, 1, 1, 12, tzinfo=ZoneInfo("Europe/London")
            )
            result = self._scrape(
                [self._product("PreOrder", c_releaseDate="2026-11-12")]
            )
        assert result[0]["Release"] == "12 Nov 2026"

    def test_release_date_today_is_kept(self):
        today = _uk_today()
        result = self._scrape([self._product(c_releaseDate=today.isoformat())])
        assert "Release" in result[0]

    def test_past_release_date_is_omitted(self):
        past = _uk_today() - timedelta(days=1)
        result = self._scrape([self._product(c_releaseDate=past.isoformat())])
        assert "Release" not in result[0]

    @pytest.mark.parametrize("value", [None, "", "garbage", "2026-13-45", 20261112, []])
    def test_missing_or_bad_release_date_is_omitted(self, value):
        result = self._scrape([self._product(c_releaseDate=value)])
        assert len(result) == 1
        assert "Release" not in result[0]

    def test_missing_release_key_is_omitted(self):
        result = self._scrape([self._product()])
        assert "Release" not in result[0]


class TestStockistIntegration:
    """Integration tests for stockist module."""

    def test_all_stockists_have_required_attributes(self):
        """Test all stockists have required attributes."""
        for stockist_class in STOCKIST_FACTORY.values():
            stockist = stockist_class(messengers=["test"])

            assert hasattr(stockist, "name")
            assert hasattr(stockist, "base_url")
            assert hasattr(stockist, "params")
            assert hasattr(stockist, "get_amiibo")
            assert hasattr(stockist, "scrape")

            assert stockist.name is not None
            assert stockist.base_url is not None


class TestSessionRetryConfig:
    @pytest.fixture(autouse=True)
    def fresh_session(self):
        import stockist.utils as su

        original = su._session
        su._session = None
        yield
        su._session = original

    def test_adapter_mounted_with_retry_config(self):
        from requests.adapters import HTTPAdapter

        from stockist.utils import _get_session

        session = _get_session()
        for prefix in ("https://", "http://"):
            adapter = session.get_adapter(prefix + "example.com")
            assert isinstance(adapter, HTTPAdapter)
            retry = adapter.max_retries
            assert retry.total == 2
            assert retry.backoff_factor == 1
            assert tuple(retry.status_forcelist) == (429, 500, 502, 503, 504)
            assert set(retry.allowed_methods) == {"GET"}
            assert retry.respect_retry_after_header is False
            assert retry.raise_on_status is False

    def test_session_is_shared_and_has_no_content_type_header(self):
        from stockist.utils import _get_session

        session = _get_session()
        assert _get_session() is session
        assert "Content-Type" not in session.headers
        assert "User-Agent" in session.headers

    def test_session_sends_browser_like_headers(self):
        from stockist.utils import _get_session

        session = _get_session()
        assert "text/html" in session.headers["Accept"]
        assert "application/json" in session.headers["Accept"]
        assert session.headers["Accept-Language"] == "en-GB,en;q=0.9"

    def test_user_agent_still_rotates_alongside_the_headers(self):
        from constants import FALLBACK_USER_AGENTS
        from stockist.utils import _get_session

        for _ in range(5):
            session = _get_session()
            assert session.headers["User-Agent"] in FALLBACK_USER_AGENTS
            assert session.headers["Accept-Language"] == "en-GB,en;q=0.9"

    @patch("stockist.utils._get_session")
    def test_request_timeout_can_be_overridden(self, mock_session_fn):
        mock_session = Mock()
        mock_session.get.return_value = Mock(status_code=200, content=b"ok")
        mock_session_fn.return_value = mock_session

        send_public_request(url="https://test.com", timeout=30)
        assert mock_session.get.call_args.kwargs["timeout"] == 30

        send_public_request(url="https://test.com")
        assert mock_session.get.call_args.kwargs["timeout"] == REQUEST_TIMEOUT

    @patch("stockist.utils._get_session")
    def test_final_5xx_still_becomes_blank_response(self, mock_session_fn, caplog):
        from stockist.utils import BlankResponse

        response = requests.Response()
        response.status_code = 503
        response.url = "https://test.com"
        mock_session = Mock()
        mock_session.get.return_value = response
        mock_session_fn.return_value = mock_session

        with caplog.at_level("WARNING", logger="stockist.utils"):
            result = send_public_request(url="https://test.com")

        assert isinstance(result, BlankResponse)
        assert "HTTP error" in caplog.text

    @patch("stockist.utils._get_session")
    def test_retry_error_becomes_blank_response(self, mock_session_fn, caplog):
        from stockist.utils import BlankResponse

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.RetryError("too many 503")
        mock_session_fn.return_value = mock_session

        with caplog.at_level("WARNING", logger="stockist.utils"):
            result = send_public_request(url="https://test.com")

        assert isinstance(result, BlankResponse)
        assert "Retries exhausted" in caplog.text
