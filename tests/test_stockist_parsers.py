"""
Unit tests for stockist HTML/JSON parsers.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from stockist.bestbuyca import BestbuyCA
from stockist.cexuk import CexUK
from stockist.gamestop import Gamestop
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto
from stockist.stockist import Stock

FIXTURES = Path(__file__).parent / "fixtures"


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

    def test_empty_response_logs_a_clear_error(self, stockist, caplog):
        from stockist.utils import BlankResponse

        with (
            patch.object(CexUK, "scrape", return_value=BlankResponse()),
            caplog.at_level("ERROR", logger="stockist.cexuk"),
        ):
            result = stockist.get_amiibo()

        assert result == []
        assert "request failed or returned nothing" in caplog.text

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
    """Test Bestbuy CA JSON parsers."""

    @pytest.fixture
    def stockist(self):
        return BestbuyCA(messengers=["test_messenger"])

    @staticmethod
    def _release_ms(days_ahead: int) -> int:
        """Midnight Pacific time, `days_ahead` days from now, as epoch milliseconds."""
        tz = ZoneInfo("America/Vancouver")
        day = datetime.now(tz).date() + timedelta(days=days_ahead)
        return int(datetime(day.year, day.month, day.day, tzinfo=tz).timestamp() * 1000)

    @classmethod
    def _product(cls, sku="1", name="Test Amiibo", **extra):
        product = {
            "sku": sku,
            "salePrice": 19.99,
            "name": name,
            "thumbnailImage": "https://img.test/a.jpg",
            "productUrl": f"/en-ca/product/test/{sku}",
            "isPreorderable": False,
            "preorderReleaseDate": None,
        }
        product.update(extra)
        return product

    @staticmethod
    def _response(payload):
        response = Mock()
        response.content = json.dumps(payload).encode()
        return response

    @classmethod
    def _availability(cls, **purchasable):
        """An availability response; keys are SKUs, values are purchasable flags."""
        return cls._response(
            {
                "availabilities": [
                    {"sku": sku, "shipping": {"purchasable": can_buy}}
                    for sku, can_buy in purchasable.items()
                ]
            }
        )

    def _run(self, stockist, products, availability):
        search = self._response({"products": products})
        with patch.object(
            BestbuyCA, "scrape", side_effect=[search, availability]
        ) as mock_scrape:
            return stockist.get_amiibo(), mock_scrape

    def test_happy_path(self, stockist):
        products = [
            self._product(sku="1"),
            self._product(
                sku="2", name="  Second  ", salePrice="on sale", productUrl="/two"
            ),
        ]
        result, _ = self._run(
            stockist, products, self._availability(**{"1": True, "2": True})
        )

        assert len(result) == 2
        assert result[0]["Price"] == "$19.99"
        assert result[0]["Title"] == "Test Amiibo"
        assert result[0]["URL"] == "https://www.bestbuy.ca/en-ca/product/test/1"
        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert result[0]["Colour"] == 0x00FF00
        assert "Release" not in result[0]
        assert result[1]["Title"] == "Second"
        assert result[1]["Price"] == "on sale"
        assert result[1]["URL"] == "https://www.bestbuy.ca/two"

    def test_uses_a_longer_timeout_than_the_default(self, stockist):
        assert stockist.request_timeout > 5

    def test_availability_request_lists_skus(self, stockist):
        products = [self._product(sku="11"), self._product(sku="22")]
        _, mock_scrape = self._run(
            stockist, products, self._availability(**{"11": True, "22": True})
        )

        assert mock_scrape.call_count == 2
        availability_call = mock_scrape.call_args_list[1].kwargs
        assert availability_call["url"].endswith("/availability/products")
        assert availability_call["payload"]["skus"] == "11|22"

    def test_sold_out_item_is_out_of_stock(self, stockist):
        products = [self._product(sku="1"), self._product(sku="2")]
        result, _ = self._run(
            stockist, products, self._availability(**{"1": True, "2": False})
        )

        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert result[1]["Stock"] == Stock.OUT_OF_STOCK.value
        assert result[1]["Colour"] == 0xFF0000

    def test_preorder_is_pre_order_with_release_date(self, stockist):
        release_ms = self._release_ms(30)
        release = datetime.fromtimestamp(
            release_ms / 1000, ZoneInfo("America/Vancouver")
        )
        products = [
            self._product(sku="1", isPreorderable=True, preorderReleaseDate=release_ms)
        ]
        result, _ = self._run(stockist, products, self._availability(**{"1": True}))

        assert result[0]["Stock"] == Stock.PRE_ORDER.value
        assert result[0]["Colour"] == 0xFFA500
        assert result[0]["Release"] == f"{release.day} {release.strftime('%b %Y')}"

    def test_sold_out_preorder_is_out_of_stock_but_keeps_release_date(self, stockist):
        products = [
            self._product(
                sku="1", isPreorderable=True, preorderReleaseDate=self._release_ms(30)
            )
        ]
        result, _ = self._run(stockist, products, self._availability(**{"1": False}))

        assert result[0]["Stock"] == Stock.OUT_OF_STOCK.value
        assert "Release" in result[0]

    def test_past_release_date_is_omitted(self, stockist):
        products = [
            self._product(
                sku="1", isPreorderable=True, preorderReleaseDate=self._release_ms(-30)
            )
        ]
        result, _ = self._run(stockist, products, self._availability(**{"1": True}))

        assert result[0]["Stock"] == Stock.PRE_ORDER.value
        assert "Release" not in result[0]

    def test_release_date_ignored_when_not_preorderable(self, stockist):
        # The API keeps the old release date on ordinary items.
        products = [self._product(sku="1", preorderReleaseDate=self._release_ms(30))]
        result, _ = self._run(stockist, products, self._availability(**{"1": True}))

        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert "Release" not in result[0]

    @pytest.mark.parametrize("bad_response", [b"", b"not json", b'{"other": 1}'])
    def test_availability_failure_falls_back_to_in_stock(
        self, stockist, bad_response, caplog
    ):
        availability = Mock()
        availability.content = bad_response
        products = [
            self._product(sku="1"),
            self._product(sku="2", isPreorderable=True),
        ]

        with caplog.at_level("WARNING", logger="stockist.bestbuyca"):
            result, _ = self._run(stockist, products, availability)

        assert [item["Stock"] for item in result] == [
            Stock.IN_STOCK.value,
            Stock.PRE_ORDER.value,
        ]
        assert "assuming listed items are in stock" in caplog.text

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

    def test_empty_response_logs_a_clear_error(self, stockist, caplog):
        from stockist.utils import BlankResponse

        with (
            patch.object(BestbuyCA, "scrape", return_value=BlankResponse()),
            caplog.at_level("ERROR", logger="stockist.bestbuyca"),
        ):
            result = stockist.get_amiibo()

        assert result == []
        assert "request failed or returned nothing" in caplog.text
        assert "decode" not in caplog.text

    def test_no_products_key(self, stockist):
        mock_response = Mock()
        mock_response.content = b'{"other": 1}'
        with patch.object(BestbuyCA, "scrape", return_value=mock_response) as scrape:
            result = stockist.get_amiibo()

        assert result == []
        scrape.assert_called_once()

    def test_live_shaped_payload(self, stockist):
        """A trimmed copy of the real search and availability responses."""
        search = Mock()
        search.content = (FIXTURES / "bestbuyca_search.json").read_bytes()
        availability = Mock()
        availability.content = (FIXTURES / "bestbuyca_availability.json").read_bytes()
        with patch.object(BestbuyCA, "scrape", side_effect=[search, availability]):
            result = stockist.get_amiibo()

        assert [item["Stock"] for item in result] == [
            Stock.IN_STOCK.value,
            Stock.PRE_ORDER.value,
            Stock.OUT_OF_STOCK.value,
            Stock.OUT_OF_STOCK.value,
        ]
        assert all(item["URL"].startswith("https://www.bestbuy.ca/") for item in result)
        assert result[1]["Release"] == "1 Jan 2100"
        assert "Release" not in result[0]


class TestGamestop:
    """Test Gamestop HTML parser."""

    @pytest.fixture
    def stockist(self):
        return Gamestop(messengers=["test_messenger"])

    @pytest.fixture
    def tiles(self):
        return (FIXTURES / "gamestop_tiles.html").read_bytes()

    def test_params_ask_for_everything_with_no_stock_filter(self, stockist):
        assert stockist.params == {"start": 0, "sz": 300}

    def test_waits_for_tiles_and_passes_payload(self, stockist, tiles):
        with patch.object(
            Gamestop, "scrape_with_selenium", return_value=tiles
        ) as mock_selenium:
            stockist.get_amiibo()

        mock_selenium.assert_called_once()
        kwargs = mock_selenium.call_args.kwargs
        assert kwargs["payload"] == stockist.params
        assert kwargs["wait_for"] == "div.product.grid-tile"

    def test_parses_real_tiles(self, stockist, tiles):
        with patch.object(Gamestop, "scrape_with_selenium", return_value=tiles):
            result = stockist.get_amiibo()

        by_title = {item["Title"]: item for item in result}
        assert len(result) == 5

        in_stock = by_title["The Legend of Zelda: Ocarina of Time Link amiibo"]
        assert in_stock["Stock"] == Stock.IN_STOCK.value
        assert in_stock["Colour"] == 0x00FF00
        assert in_stock["Price"] == "$59.99"
        assert in_stock["URL"].startswith("https://www.gamestop.com/consoles-hardware/")
        assert in_stock["URL"].endswith("/405998.html")
        assert in_stock["Image"].startswith("https://media.gamestop.com/i/gamestop/")
        assert "Release" not in in_stock

        for item in result:
            assert item["Website"] == "Gamestop US"
            assert item["URL"].startswith("https://")
            assert item["Image"].startswith("https://")

    def test_future_release_is_pre_order_with_release_date(self, stockist, tiles):
        with patch.object(Gamestop, "scrape_with_selenium", return_value=tiles):
            result = stockist.get_amiibo()

        kirby = next(item for item in result if item["Title"].startswith("Kirby"))
        assert kirby["Stock"] == Stock.PRE_ORDER.value
        assert kirby["Colour"] == 0xFFA500
        assert kirby["Release"] == "31 Dec 2099"

    def test_unavailable_item_is_out_of_stock(self, stockist, tiles):
        with patch.object(Gamestop, "scrape_with_selenium", return_value=tiles):
            result = stockist.get_amiibo()

        young_link = next(item for item in result if "Young Link" in item["Title"])
        assert young_link["Stock"] == Stock.OUT_OF_STOCK.value
        assert young_link["Colour"] == 0xFF0000

    def test_falls_back_to_visible_markup(self, stockist, tiles):
        with patch.object(Gamestop, "scrape_with_selenium", return_value=tiles):
            result = stockist.get_amiibo()

        fallback = next(
            item for item in result if item["Title"] == "Markup Only amiibo"
        )
        assert fallback["Price"] == "$34.99"
        assert fallback["Stock"] == Stock.IN_STOCK.value
        assert fallback["URL"].startswith("https://www.gamestop.com/")
        assert fallback["Image"].startswith("https://media.gamestop.com/")

    def test_sale_price_is_preferred_over_base_price(self, stockist):
        gtm = json.dumps(
            {
                "name": "Sale amiibo",
                "url": "/p/sale.html",
                "price": {"base": "30.00", "sale": "20.5"},
                "availability": {"available": True, "preorder": None},
                "releaseDate": None,
                "image": {"base": "https://media.gamestop.com/i/gamestop/1?"},
            }
        )
        html = f"""<div class="product grid-tile"><a data-gtmdata='{gtm}' href="/p/sale.html"></a></div>"""
        with patch.object(Gamestop, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result[0]["Price"] == "$20.50"

    def test_preorder_flag_is_pre_order(self, stockist):
        gtm = json.dumps(
            {
                "name": "Early amiibo",
                "url": "https://www.gamestop.com/p/early.html",
                "price": {"base": "30.00", "sale": None},
                "availability": {"available": True, "preorder": {"date": "soon"}},
                "releaseDate": None,
                "image": {"base": "https://media.gamestop.com/i/gamestop/1?"},
            }
        )
        html = f"""<div class="product grid-tile"><a data-gtmdata='{gtm}' href="/p/early.html"></a></div>"""
        with patch.object(Gamestop, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result[0]["Stock"] == Stock.PRE_ORDER.value
        assert result[0]["URL"] == "https://www.gamestop.com/p/early.html"

    def test_past_release_date_is_omitted(self, stockist):
        gtm = json.dumps(
            {
                "name": "Old amiibo",
                "url": "/p/old.html",
                "price": {"base": "30.00", "sale": None},
                "availability": {"available": True, "preorder": None},
                "releaseDate": "01/02/2020",
                "image": {"base": "https://media.gamestop.com/i/gamestop/1?"},
            }
        )
        html = f"""<div class="product grid-tile"><a data-gtmdata='{gtm}' href="/p/old.html"></a></div>"""
        with patch.object(Gamestop, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result[0]["Stock"] == Stock.IN_STOCK.value
        assert "Release" not in result[0]

    def test_skip_card_with_missing_fields(self, stockist):
        html = """
        <div class="product grid-tile">
            <div class="render-tile-name">No price</div>
        </div>
        <div class="product grid-tile">
            <a data-gtmdata="not json" href="/p/x.html"></a>
        </div>
        """
        with patch.object(Gamestop, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result == []

    def test_duplicate_tiles_are_listed_once(self, stockist, tiles):
        with patch.object(Gamestop, "scrape_with_selenium", return_value=tiles + tiles):
            result = stockist.get_amiibo()

        assert len(result) == 5

    def test_empty_page_logs_a_clear_error(self, stockist, caplog):
        with (
            patch.object(Gamestop, "scrape_with_selenium", return_value=""),
            patch.object(Gamestop, "scrape") as mock_scrape,
            caplog.at_level("ERROR", logger="stockist.gamestop"),
        ):
            result = stockist.get_amiibo()

        assert result == []
        assert "request failed or returned nothing" in caplog.text
        mock_scrape.assert_not_called()

    def test_page_without_tiles_returns_empty(self, stockist, caplog):
        with (
            patch.object(
                Gamestop, "scrape_with_selenium", return_value="<html></html>"
            ),
            caplog.at_level("WARNING", logger="stockist.gamestop"),
        ):
            result = stockist.get_amiibo()

        assert result == []
        assert "no product tiles" in caplog.text


class TestPlayAsia:
    """Test Play-Asia HTML parser."""

    @pytest.fixture
    def stockist(self):
        return PlayAsia(messengers=["test_messenger"])

    @pytest.fixture
    def page(self):
        return (FIXTURES / "playasia_page.html").read_bytes()

    def test_base_url_has_no_fragment(self, stockist):
        assert "#" not in stockist.base_url

    def test_parses_real_markup(self, stockist, page):
        with patch.object(PlayAsia, "scrape_with_selenium", return_value=page):
            result = stockist.get_amiibo()

        # Four real products; one has no price and one is a skeleton placeholder.
        assert len(result) == 3
        first = result[0]
        assert first["Title"].startswith("amiibo ")
        assert first["Price"].startswith("£")
        assert " " not in first["Price"]
        assert first["Image"].startswith("https://s.pacn.ws/")
        assert first["URL"].startswith("https://www.play-asia.com/en/")
        assert first["Stock"] == Stock.IN_STOCK.value
        assert first["Colour"] == 0x00FF00
        assert first["Website"] == "Playasia"

    def test_pre_order_icon_is_pre_order(self, stockist, page):
        with patch.object(PlayAsia, "scrape_with_selenium", return_value=page):
            result = stockist.get_amiibo()

        pre_orders = [i for i in result if i["Stock"] == Stock.PRE_ORDER.value]
        assert len(pre_orders) == 1
        assert pre_orders[0]["Colour"] == 0xFFA500

    def test_item_without_add_to_cart_is_out_of_stock(self, stockist):
        html = """
        <div class="pa-modern-product-item">
            <div class="pa-modern-product-image"><a href="/en/x/13/1"><img src="//img.test/x.jpg"/></a></div>
            <h3 class="pa-modern-product-title"><a href="/en/x/13/1">amiibo Sold Out</a></h3>
            <span class="pa-modern-current-price"><span>£</span><span class="price_val">9.99</span></span>
        </div>
        """
        with patch.object(PlayAsia, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result[0]["Stock"] == Stock.OUT_OF_STOCK.value
        assert result[0]["Colour"] == 0xFF0000
        assert result[0]["Price"] == "£9.99"
        assert result[0]["Image"] == "https://img.test/x.jpg"

    def test_skeleton_placeholders_are_ignored(self, stockist):
        html = """
        <div class="pa-modern-product-item pa-skeleton-item">
            <div class="pa-skeleton-product-title"></div>
        </div>
        """
        with patch.object(PlayAsia, "scrape_with_selenium", return_value=html):
            result = stockist.get_amiibo()

        assert result == []

    def test_uses_selenium_only_and_never_requests(self, stockist, page):
        with (
            patch.object(
                PlayAsia, "scrape_with_selenium", return_value=page
            ) as mock_selenium,
            patch.object(PlayAsia, "scrape") as mock_scrape,
        ):
            stockist.get_amiibo()

        mock_selenium.assert_called()
        mock_scrape.assert_not_called()

    def test_fetches_each_page_through_the_fragment(self, stockist, page):
        # The fixture says there are 6 pages.
        with patch.object(
            PlayAsia, "scrape_with_selenium", return_value=page
        ) as mock_selenium:
            stockist.get_amiibo()

        urls = [call.kwargs["url"] for call in mock_selenium.call_args_list]
        assert urls == [f"{stockist.base_url}#fc=p:{n}" for n in range(1, 7)]
        assert all(
            call.kwargs["wait_for"]
            == "div.pa-modern-product-item:not(.pa-skeleton-item)"
            for call in mock_selenium.call_args_list
        )

    def test_single_page_is_fetched_once(self, stockist, page):
        one_page = page.replace(
            b'<span class="pa-pagination-total">6</span>',
            b'<span class="pa-pagination-total">1</span>',
        )
        with patch.object(
            PlayAsia, "scrape_with_selenium", return_value=one_page
        ) as mock_selenium:
            stockist.get_amiibo()

        mock_selenium.assert_called_once()

    def test_page_count_is_capped(self, stockist, page):
        many = page.replace(
            b'<span class="pa-pagination-total">6</span>',
            b'<span class="pa-pagination-total">500</span>',
        )
        with patch.object(
            PlayAsia, "scrape_with_selenium", return_value=many
        ) as mock_selenium:
            stockist.get_amiibo()

        assert mock_selenium.call_count == 10

    def test_same_item_on_two_pages_is_listed_once(self, stockist, page):
        with patch.object(PlayAsia, "scrape_with_selenium", return_value=page):
            result = stockist.get_amiibo()

        assert len(result) == len({item["URL"] for item in result}) == 3

    def test_stops_when_a_page_fails(self, stockist, page, caplog):
        with (
            patch.object(PlayAsia, "scrape_with_selenium", side_effect=[page, ""]),
            caplog.at_level("ERROR", logger="stockist.playasia"),
        ):
            result = stockist.get_amiibo()

        assert len(result) == 3
        assert "page 2 failed or returned nothing" in caplog.text

    def test_empty_first_page_returns_empty(self, stockist, caplog):
        with (
            patch.object(PlayAsia, "scrape_with_selenium", return_value=""),
            caplog.at_level("ERROR", logger="stockist.playasia"),
        ):
            result = stockist.get_amiibo()

        assert result == []
        assert "page 1 failed or returned nothing" in caplog.text

    def test_page_with_no_products_stops(self, stockist, caplog):
        with (
            patch.object(
                PlayAsia, "scrape_with_selenium", return_value="<html></html>"
            ) as mock_selenium,
            caplog.at_level("WARNING", logger="stockist.playasia"),
        ):
            result = stockist.get_amiibo()

        assert result == []
        mock_selenium.assert_called_once()
        assert "no products found on page 1" in caplog.text


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
