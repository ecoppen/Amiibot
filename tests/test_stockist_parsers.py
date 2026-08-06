"""
Unit tests for stockist HTML/JSON parsers.
"""

import pytest
from unittest.mock import Mock, patch

from stockist.stockist import Stock
from stockist.bestbuyca import BestbuyCA
from stockist.cexuk import CexUK
from stockist.game import Game
from stockist.gamestop import Gamestop
from stockist.mecchajapan import MecchaJapan
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto
from stockist.thesource import TheSource


class TestTheSource:
    """Test TheSource HTML parser."""

    @pytest.fixture
    def stockist(self):
        return TheSource(messengers=["test_messenger"])

    CARD_HTML = b"""
    <div class="productListItem">
        <div class="productMainLink"><span>Test Amiibo</span></div>
        <button>Add to Cart</button>
        <div class="sale-price">$19.99</div>
        <img class="primary-image" src="/images/test.jpg" />
        <a href="/product/test-amiibo">link</a>
    </div>
    """

    def test_happy_path_in_stock(self, stockist):
        mock_response = Mock()
        mock_response.content = self.CARD_HTML
        with patch.object(TheSource, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert len(result) == 2
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["Price"] == "$19.99"
        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert result[0]["Colour"] == 0x00FF00
        assert result[0]["URL"] == "https://www.thesource.ca//product/test-amiibo"
        assert result[0]["Image"] == "https://www.thesource.ca//images/test.jpg"

    def test_out_of_stock_button(self, stockist):
        html = self.CARD_HTML.replace(b"Add to Cart", b"Out of stock")
        mock_response = Mock()
        mock_response.content = html
        with patch.object(TheSource, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result[0]["Stock"] == Stock.OUT_OF_STOCK.value
        assert result[0]["Colour"] == 0xFF0000

    def test_skip_card_with_missing_fields(self, stockist):
        html = b"""
        <div class="productListItem">
            <div class="productMainLink"><span>No price</span></div>
            <button>Add to Cart</button>
        </div>
        """
        mock_response = Mock()
        mock_response.content = html
        with patch.object(TheSource, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_selenium_fallback_when_no_cards(self, stockist):
        mock_response = Mock()
        mock_response.content = b"<html></html>"
        with (
            patch.object(TheSource, "scrape", return_value=mock_response),
            patch.object(
                TheSource, "scrape_with_selenium", return_value=self.CARD_HTML
            ) as mock_selenium,
        ):
            result = stockist.get_amiibo()

        assert mock_selenium.call_count == 2
        assert len(result) == 2


class TestCexUK:
    """Test CeX UK JSON parser."""

    @pytest.fixture
    def stockist(self):
        return CexUK(messengers=["test_messenger"])

    BOXES_JSON = b"""
    {
        "response": {
            "data": {
                "boxes": [
                    {
                        "boxName": "Test Amiibo",
                        "imageUrls": {"medium": "https://img.test/a.jpg"},
                        "boxId": "12345",
                        "sellPrice": "19.99"
                    }
                ]
            }
        }
    }
    """

    def test_happy_path(self, stockist):
        null_json = b'{"response": {"data": null}}'
        mock_response = Mock()
        mock_response.content = self.BOXES_JSON
        mock_null = Mock()
        mock_null.content = null_json
        with patch.object(
            CexUK,
            "scrape",
            side_effect=[mock_response, mock_null, mock_response, mock_null],
        ):
            result = stockist.get_amiibo()

        assert len(result) == 2
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["URL"] == "https://uk.webuy.com/product-detail/?id=12345"
        assert result[0]["Price"] == "£19.99"
        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert stockist.params["firstRecord"] == 51

    def test_invalid_json_returns_empty(self, stockist):
        mock_response = Mock()
        mock_response.content = b"not json"
        with patch.object(CexUK, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_attributes_error_returns_empty(self, stockist):
        mock_response = Mock()
        mock_response.content = None
        with patch.object(CexUK, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_missing_boxes_key_breaks(self, stockist):
        no_boxes = b'{"response": {"data": {"other": 1}}}'
        mock_response = Mock()
        mock_response.content = no_boxes
        with patch.object(CexUK, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_missing_response_key_breaks(self, stockist):
        mock_response = Mock()
        mock_response.content = b'{"other": 1}'
        with patch.object(CexUK, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []


class TestBestbuyCA:
    """Test Bestbuy CA JSON parser."""

    @pytest.fixture
    def stockist(self):
        return BestbuyCA(messengers=["test_messenger"])

    PRODUCTS_JSON = b"""
    {
        "products": [
            {
                "salePrice": 19.99,
                "name": "Test Amiibo",
                "thumbnailImage": "https://img.test/a.jpg",
                "productUrl": "/product/test"
            },
            {
                "salePrice": "on sale",
                "name": "  Second  ",
                "thumbnailImage": "img2.jpg",
                "productUrl": "/product/two"
            }
        ]
    }
    """

    def test_happy_path(self, stockist):
        mock_response = Mock()
        mock_response.content = self.PRODUCTS_JSON
        with patch.object(BestbuyCA, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert len(result) == 2
        assert result[0]["Price"] == "$19.99"
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["URL"] == "https://www.bestbuy.ca/product/test"
        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert result[1]["Title"] == "Second"
        assert result[1]["Price"] == "on sale"

    def test_invalid_json_returns_empty(self, stockist):
        mock_response = Mock()
        mock_response.content = b"not json"
        with patch.object(BestbuyCA, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_attributes_error_returns_empty(self, stockist):
        mock_response = Mock()
        mock_response.content = None
        with patch.object(BestbuyCA, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_no_products_key(self, stockist):
        mock_response = Mock()
        mock_response.content = b'{"other": 1}'
        with patch.object(BestbuyCA, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []


class TestGame:
    """Test Game UK HTML parser."""

    @pytest.fixture
    def stockist(self):
        return Game(messengers=["test_messenger"])

    CARD_HTML = b"""
    <article class="product">
        <a href="/category">category</a>
        <a href="https://www.game.co.uk/product/test">Test Amiibo</a>
        <span class="value">19.99</span>
        <img class="optimisedImg" src="https://img.test/a.jpg" />
    </article>
    """

    def test_happy_path(self, stockist):
        mock_response = Mock()
        mock_response.content = self.CARD_HTML
        with patch.object(Game, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert len(result) == 1
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["Price"] == "19.99"
        assert result[0]["URL"] == "https://www.game.co.uk/product/test"
        assert result[0]["Stock"] == Stock.IN_STOCK.value

    def test_skip_card_with_missing_fields(self, stockist):
        mock_response = Mock()
        mock_response.content = b"""
        <article class="product">
            <a href="/category">category</a>
            <a href="/product/test">No price</a>
        </article>
        """
        with patch.object(Game, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_selenium_fallback_when_no_cards(self, stockist):
        mock_response = Mock()
        mock_response.content = b"<html></html>"
        with (
            patch.object(Game, "scrape", return_value=mock_response),
            patch.object(
                Game, "scrape_with_selenium", return_value=self.CARD_HTML
            ) as mock_selenium,
        ):
            result = stockist.get_amiibo()

        mock_selenium.assert_called_once()
        assert len(result) == 1


class TestGamestop:
    """Test Gamestop HTML parser."""

    @pytest.fixture
    def stockist(self):
        return Gamestop(messengers=["test_messenger"])

    CARD_HTML = b"""
    <div class="product grid-tile">
        <p class="pd-name">Test Amiibo</p>
        <span class="actual-price">$19.99</span>
        <img class="tile-image" src="https://img.test/a.jpg" />
        <a class="product-tile-link" href="/product/test">link</a>
    </div>
    """

    def test_happy_path(self, stockist):
        with patch.object(
            Gamestop, "scrape_with_selenium", return_value=self.CARD_HTML
        ):
            result = stockist.get_amiibo()

        assert len(result) == 1
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["URL"] == "https://www.gamestop.com/product/test"
        assert result[0]["Stock"] == Stock.IN_STOCK.value

    def test_selenium_failure_falls_back_to_requests(self, stockist):
        mock_response = Mock()
        mock_response.content = self.CARD_HTML
        with (
            patch.object(
                Gamestop, "scrape_with_selenium", return_value="<html></html>"
            ),
            patch.object(Gamestop, "scrape", return_value=mock_response) as mock_scrape,
        ):
            result = stockist.get_amiibo()

        mock_scrape.assert_called_once()
        assert len(result) == 1

    def test_skip_card_with_missing_fields(self, stockist):
        html = b"""
        <div class="product grid-tile">
            <p class="pd-name">No price</p>
        </div>
        """
        with patch.object(Gamestop, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result == []


class TestMecchaJapan:
    """Test Meccha Japan HTML parser."""

    @pytest.fixture
    def stockist(self):
        return MecchaJapan(messengers=["test_messenger"])

    CARD_HTML = b"""
    <article class="product-miniature">
        <h2 class="product-title"><a href="/en/test-amiibo">Test Amiibo</a></h2>
        <span class="price">$29.99</span>
        <img src="https://img.test/a.jpg" />
        <a href="/en/test-amiibo">link</a>
    </article>
    """

    def test_happy_path(self, stockist):
        mock_response = Mock()
        mock_response.content = self.CARD_HTML
        with patch.object(MecchaJapan, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert len(result) == 4
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["Price"] == "$29.99"
        assert result[0]["Stock"] == Stock.IN_STOCK.value

    def test_out_of_stock_label_skipped(self, stockist):
        html = self.CARD_HTML.replace(
            b'<a href="/en/test-amiibo">link</a>',
            b'<div class="oos-label">Out of stock</div>',
        )
        mock_response = Mock()
        mock_response.content = html
        with patch.object(MecchaJapan, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_skip_card_without_header(self, stockist):
        html = (
            b"<article class='product-miniature'><span class='price'>x</span></article>"
        )
        mock_response = Mock()
        mock_response.content = html
        with patch.object(MecchaJapan, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_selenium_fallback_when_no_cards(self, stockist):
        mock_response = Mock()
        mock_response.content = b"<html></html>"
        with (
            patch.object(MecchaJapan, "scrape", return_value=mock_response),
            patch.object(
                MecchaJapan, "scrape_with_selenium", return_value=self.CARD_HTML
            ) as mock_selenium,
        ):
            result = stockist.get_amiibo()

        mock_selenium.assert_called()
        assert len(result) == 4


class TestPlayAsia:
    """Test Play-Asia HTML parser."""

    @pytest.fixture
    def stockist(self):
        return PlayAsia(messengers=["test_messenger"])

    CARD_HTML = b"""
    <div class="p_prev">
        <span class="p_prev_n">Test Amiibo</span>
        <span class="price_val">$34.99</span>
        <img class="p_prev_img" src="//img.test/a.jpg" />
        <a href="/product/test">link</a>
    </div>
    """

    def test_happy_path_deduplicates(self, stockist):
        mock_response = Mock()
        mock_response.content = self.CARD_HTML
        with patch.object(PlayAsia, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert len(result) == 1
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["Image"] == "https://img.test/a.jpg"
        assert result[0]["URL"] == "https://www.play-asia.com/product/test"
        assert result[0]["Stock"] == Stock.IN_STOCK.value

    def test_skip_card_with_missing_fields(self, stockist):
        html = b"<div class='p_prev'><span class='p_prev_n'>No price</span></div>"
        mock_response = Mock()
        mock_response.content = html
        with patch.object(PlayAsia, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_selenium_fallback_when_no_cards(self, stockist):
        mock_response = Mock()
        mock_response.content = b"<html></html>"
        with (
            patch.object(PlayAsia, "scrape", return_value=mock_response),
            patch.object(
                PlayAsia, "scrape_with_selenium", return_value=self.CARD_HTML
            ) as mock_selenium,
        ):
            result = stockist.get_amiibo()

        mock_selenium.assert_called()
        assert len(result) == 1


class TestShopto:
    """Test Shopto HTML parser."""

    @pytest.fixture
    def stockist(self):
        return Shopto(messengers=["test_messenger"])

    CARD_HTML = b"""
    <div class="itemlist2">
        <div class="itemlist__description">Test Amiibo</div>
        <div class="inventory">In stock</div>
        <div class="cross_price">&pound;24.99</div>
        <img src="/images/test.jpg" />
        <a class="itemlist__container" href="/product/test">link</a>
    </div>
    """

    def test_happy_path(self, stockist):
        mock_response = Mock()
        mock_response.content = self.CARD_HTML
        with patch.object(Shopto, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert len(result) == 1
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["Price"] == "£24.99"
        assert result[0]["URL"] == "https://www.shopto.net/product/test"
        assert result[0]["Image"] == "https://www.shopto.net/images/test.jpg"
        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert result[0]["Colour"] == 0x00FF00

    def test_sold_out(self, stockist):
        html = self.CARD_HTML.replace(b"In stock", b"Sold out")
        mock_response = Mock()
        mock_response.content = html
        with patch.object(Shopto, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result[0]["Stock"] == Stock.OUT_OF_STOCK.value
        assert result[0]["Colour"] == 0xFF0000

    def test_skip_card_with_missing_fields(self, stockist):
        html = b"""
        <div class="itemlist2">
            <div class="itemlist__description">No stock</div>
        </div>
        """
        mock_response = Mock()
        mock_response.content = html
        with patch.object(Shopto, "scrape", return_value=mock_response):
            result = stockist.get_amiibo()

        assert result == []

    def test_selenium_fallback_when_no_cards(self, stockist):
        mock_response = Mock()
        mock_response.content = b"<html></html>"
        with (
            patch.object(Shopto, "scrape", return_value=mock_response),
            patch.object(
                Shopto, "scrape_with_selenium", return_value=self.CARD_HTML
            ) as mock_selenium,
        ):
            result = stockist.get_amiibo()

        mock_selenium.assert_called_once()
        assert len(result) == 1
