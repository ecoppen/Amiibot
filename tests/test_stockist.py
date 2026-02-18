"""
Unit tests for stockist module.
"""

import pytest
from unittest.mock import Mock, patch
from stockist.stockist import Stockist, Stock
from stockist.manager import StockistManager, STOCKIST_FACTORY
from stockist.useragents import UserAgent
from stockist.utils import send_public_request
from stockist.bestbuy import Bestbuy
from stockist.bestbuyca import BestbuyCA
from stockist.cexuk import CexUK
from stockist.game import Game
from stockist.gamestop import Gamestop
from stockist.mecchajapan import MecchaJapan
from stockist.nintendouk import NintendoUK
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto
from stockist.thesource import TheSource
import requests


class TestStock:
    """Test Stock enumeration."""

    def test_stock_enum_values(self):
        """Test Stock enum has correct values."""
        assert Stock.DELISTED.value == "Delisted"
        assert Stock.IN_STOCK.value == "In stock"
        assert Stock.OUT_OF_STOCK.value == "Out of Stock"
        assert Stock.PRICE_CHANGE.value == "Price change"

    def test_stock_enum_members(self):
        """Test Stock enum has all expected members."""
        expected_members = ["DELISTED", "IN_STOCK", "OUT_OF_STOCK", "PRICE_CHANGE"]
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
            url="https://test.com", payload={"key": "value"}
        )


class TestUserAgent:
    """Test UserAgent class."""

    def test_useragent_initialization(self):
        """Test UserAgent initializes correctly."""
        ua = UserAgent()
        assert ua.base_agents is not None

    def test_get_user_agents(self):
        """Test get_user_agents returns list."""
        ua = UserAgent()
        agents = ua.get_user_agents()
        assert isinstance(agents, list)
        # Should have at least some user agents
        assert len(agents) > 0

    def test_user_agents_are_strings(self):
        """Test that all user agents are strings."""
        ua = UserAgent()
        agents = ua.get_user_agents()
        for agent in agents:
            assert isinstance(agent, str)
            assert len(agent) > 0


class TestStockistUtils:
    """Test stockist utility functions."""

    @patch("stockist.utils.dispatch_request")
    def test_send_public_request_success(self, mock_dispatch):
        """Test successful public request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Success"

        mock_get = Mock(return_value=mock_response)
        mock_dispatch.return_value = mock_get

        result = send_public_request(url="https://test.com", payload={"key": "value"})

        assert result == mock_response
        mock_dispatch.assert_called_once_with("GET")

    @patch("stockist.utils.dispatch_request")
    def test_send_public_request_timeout(self, mock_dispatch):
        """Test request timeout handling."""
        from stockist.utils import BlankResponse

        mock_get = Mock(side_effect=requests.exceptions.Timeout)
        mock_dispatch.return_value = mock_get

        result = send_public_request(url="https://test.com", payload=None)

        # Should return BlankResponse
        assert isinstance(result, BlankResponse)

    @patch("stockist.utils.dispatch_request")
    def test_send_public_request_connection_error(self, mock_dispatch):
        """Test connection error handling."""
        from stockist.utils import BlankResponse

        mock_get = Mock(side_effect=requests.exceptions.ConnectionError)
        mock_dispatch.return_value = mock_get

        result = send_public_request(url="https://test.com", payload=None)

        # Should return BlankResponse
        assert isinstance(result, BlankResponse)


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
            "game.co.uk",
            "meccha-japan.com",
            "nintendo.co.uk",
            "play-asia.com",
            "shopto.net",
            "thesource.ca",
            "uk.webuy.com",
        ]

        for stockist in expected_stockists:
            assert stockist in STOCKIST_FACTORY

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
        (Game, "Game UK", "https://www.game.co.uk/en/amiibo/"),
        (MecchaJapan, "Meccha Japan", "https://meccha-japan.com/en/367-amiibo?page="),
        (
            NintendoUK,
            "Nintendo UK",
            "https://store.nintendo.co.uk/api/catalog/products",
        ),
        (
            PlayAsia,
            "Playasia",
            "https://www.play-asia.com/games/amiibos/14/712od#fc=s:3,m:6,p:",
        ),
        (Shopto, "Shopto", "https://www.shopto.net/en/search/?input_search=amiibo"),
        (
            TheSource,
            "The Source",
            "https://www.thesource.ca/en-ca/search?q=amiibo&page=",
        ),
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


class TestStockistIntegration:
    """Integration tests for stockist module."""

    def test_all_stockists_have_required_attributes(self):
        """Test all stockists have required attributes."""
        for stockist_url, stockist_class in STOCKIST_FACTORY.items():
            stockist = stockist_class(messengers=["test"])

            assert hasattr(stockist, "name")
            assert hasattr(stockist, "base_url")
            assert hasattr(stockist, "params")
            assert hasattr(stockist, "get_amiibo")
            assert hasattr(stockist, "scrape")

            assert stockist.name is not None
            assert stockist.base_url is not None
