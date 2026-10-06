import logging
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)

SITE_URL = "https://www.play-asia.com"
ITEM_SELECTOR = "div.pa-modern-product-item:not(.pa-skeleton-item)"

# The category is listed 36 products a page. This is a safety cap on how many
# pages to fetch, in case the page count on the site is misread.
MAX_PAGES = 10

_COLOURS = {
    Stock.IN_STOCK: 0x00FF00,
    Stock.OUT_OF_STOCK: 0xFF0000,
    Stock.PRE_ORDER: 0xFFA500,
}


class PlayAsia(Stockist):
    def __init__(self, messengers: list[str]) -> None:
        super().__init__(messengers=messengers)

        self.params = None

    base_url: str = "https://www.play-asia.com/games/amiibos/14/712od"
    name: str = "Playasia"

    def _page_url(self, page: int) -> str:
        # Play-Asia handles paging in JavaScript, from a "#fc=p:<page>" fragment.
        # The fragment never reaches the server, so each page needs a browser.
        # It is used for page 1 too, so every page gets the same (default) filters.
        return f"{self.base_url}#fc=p:{page}"

    def _parse_cards(self, soup: BeautifulSoup) -> list[dict]:
        found_items = []
        for card in soup.select(ITEM_SELECTOR):
            title = card.select_one(".pa-modern-product-title")
            price = card.select_one(".pa-modern-current-price")
            link = card.select_one("a[href]")
            img = card.select_one(".pa-modern-product-image img[src]")

            if not (title and price and link and img):
                continue

            title_text = title.get_text(" ", strip=True)
            # The currency symbol and the amount sit in separate spans.
            price_text = "".join(price.get_text(strip=True).split())
            if not title_text or not any(c.isdigit() for c in price_text):
                # Items with no price (nor a buy button) cannot be bought yet.
                continue

            image = str(img["src"]).strip()
            if image.startswith("//"):
                image = f"https:{image}"

            # A pre-order is marked with a "Pre-Order" icon on the picture. Anything
            # priced but without an add-to-cart button cannot be bought right now.
            is_preorder = any(
                str(icon.get("alt", "")).strip().lower() == "pre-order"
                for icon in card.select(".pa-modern-platform-icons img")
            )
            can_buy = card.select_one(".pa-modern-add-to-cart") is not None
            if not can_buy:
                status = Stock.OUT_OF_STOCK
            elif is_preorder:
                status = Stock.PRE_ORDER
            else:
                status = Stock.IN_STOCK

            found_items.append(
                {
                    "Colour": _COLOURS[status],
                    "Title": title_text,
                    "Image": image,
                    "URL": f"{SITE_URL}{str(link['href']).strip()}",
                    "Price": price_text,
                    "Stock": status.value,
                    "Website": self.name,
                }
            )
        return found_items

    @staticmethod
    def _total_pages(soup: BeautifulSoup) -> int:
        total = soup.select_one(".pa-pagination-total")
        if isinstance(total, Tag):
            try:
                return max(1, int(total.get_text(strip=True)))
            except ValueError:
                pass
        return 1

    def get_amiibo(self) -> list[dict[str, Any]]:
        all_found: list[dict] = []
        total_pages = 1
        page = 1

        while page <= min(total_pages, MAX_PAGES):
            response = self.scrape_with_selenium(
                url=self._page_url(page), payload=self.params, wait_for=ITEM_SELECTOR
            )
            if not response:
                log.error(f"{self.name}: page {page} failed or returned nothing")
                break

            soup = BeautifulSoup(response, "html.parser")
            if page == 1:
                total_pages = self._total_pages(soup)

            items = self._parse_cards(soup)
            if not items:
                log.warning(f"{self.name}: no products found on page {page}")
                break

            for found in items:
                if found not in all_found:
                    all_found.append(found)
            page += 1

        return all_found
