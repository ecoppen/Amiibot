import json
import logging
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from bs4.element import Tag

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)

SITE_URL = "https://www.gamestop.com"
TILE_SELECTOR = "div.product.grid-tile"

# GameStop US is a US store, so "today" is the date in New York.
_US_TZ = ZoneInfo("America/New_York")


def _format_release_date(value: Any) -> str | None:
    """Format a US "MM/DD/YYYY" release date, or None unless it is today or later."""
    if not isinstance(value, str):
        return None
    try:
        month, day, year = (int(part) for part in value.strip().split("/"))
        release = date(year, month, day)
    except ValueError:
        return None
    if release < datetime.now(_US_TZ).date():
        return None
    return f"{release.day} {release.strftime('%b %Y')}"


def _absolute_url(value: str) -> str:
    return urljoin(SITE_URL + "/", value.strip())


def _thumbnail(image_url: str) -> str:
    """Ask for the tile-sized picture; the bare image URL is a ~300 KB original."""
    image_url = image_url.strip().rstrip("?")
    if not image_url:
        return ""
    return f"{image_url}?h=480&w=602&sm=clamp"


def _format_price(value: Any) -> str | None:
    """Turn a GTM price such as "34.99" into "$34.99"; None if it is unusable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return None


class Gamestop(Stockist):
    def __init__(self, messengers: list[str]) -> None:
        super().__init__(messengers=messengers)

        # `sz` is the page size and the whole amiibo category is a few hundred
        # items, so ask for them all in one go. No stock filter is applied (the
        # old "In Stock" one no longer exists and now returns nothing), so
        # out-of-stock items are listed and a restock can be spotted.
        self.params = {"start": 0, "sz": 300}

    base_url: str = "https://www.gamestop.com/consoles-hardware/nintendo-switch/nintendo-switch-amiibo"
    name: str = "Gamestop US"

    def _parse_gtm_data(self, link: Tag) -> dict[str, Any] | None:
        """Parse the tile's `data-gtmdata` JSON attribute, which has everything."""
        raw = link.get("data-gtmdata")
        if not isinstance(raw, str):
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None

        name = data.get("name")
        url = data.get("url")
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str):
            return None

        price_data = data.get("price")
        price = None
        if isinstance(price_data, dict):
            price = _format_price(price_data.get("sale")) or _format_price(
                price_data.get("base")
            )
        if price is None:
            return None

        image = data.get("image")
        image_url = image.get("base") if isinstance(image, dict) else None
        if not isinstance(image_url, str):
            image_url = ""

        availability = data.get("availability")
        availability = availability if isinstance(availability, dict) else {}
        release = _format_release_date(data.get("releaseDate"))

        if not availability.get("available"):
            status = Stock.OUT_OF_STOCK
        elif availability.get("preorder") or release is not None:
            # Still to be released, so it is being sold ahead of release.
            status = Stock.PRE_ORDER
        else:
            status = Stock.IN_STOCK

        return {
            "name": name.strip(),
            "url": url,
            "price": price,
            "image": _thumbnail(image_url),
            "status": status,
            "release": release,
        }

    def _parse_markup(self, card: Tag) -> dict[str, Any] | None:
        """Fall back to the visible tile markup if the JSON attribute is missing."""
        name = card.select_one("div.render-tile-name")
        price = card.select_one("div.render-sale-price")
        link = card.select_one("a[href]")
        image = card.select_one("div.render-tile-image")
        if not (name and price and link and image):
            return None

        name_text = name.get_text(strip=True)
        price_text = price.get_text(strip=True)
        if not name_text or not price_text:
            return None

        # The image is a CSS background: style="background-image: url(...);"
        style = image.get("style")
        image_url = ""
        if isinstance(style, str) and "url(" in style:
            image_url = style.split("url(", 1)[1].split(")", 1)[0].strip("'\" ")

        release = None
        release_tag = card.select_one("div.render-tile-release-date")
        if release_tag:
            release = _format_release_date(release_tag.get_text(strip=True))

        return {
            "name": name_text,
            "url": str(link["href"]),
            "price": price_text,
            "image": image_url,
            "status": Stock.PRE_ORDER if release is not None else Stock.IN_STOCK,
            "release": release,
        }

    def get_amiibo(self) -> list[dict[str, Any]]:
        all_found = []

        response = self.scrape_with_selenium(
            url=self.base_url, payload=self.params, wait_for=TILE_SELECTOR
        )
        if not response:
            log.error(f"{self.name}: request failed or returned nothing")
            return all_found

        soup = BeautifulSoup(response, "html.parser")
        cards = soup.select(TILE_SELECTOR)

        if len(cards) == 0:
            log.warning(f"{self.name}: no product tiles found on the page")
            return all_found

        colours = {
            Stock.IN_STOCK: 0x00FF00,
            Stock.OUT_OF_STOCK: 0xFF0000,
            Stock.PRE_ORDER: 0xFFA500,
        }

        for card in cards:
            parsed = None
            link = card.find("a", attrs={"data-gtmdata": True})
            if isinstance(link, Tag):
                parsed = self._parse_gtm_data(link)
            if parsed is None:
                parsed = self._parse_markup(card)
            if parsed is None:
                continue

            found = {
                "Colour": colours[parsed["status"]],
                "Title": parsed["name"],
                "Image": _absolute_url(parsed["image"]) if parsed["image"] else "",
                "URL": _absolute_url(parsed["url"]),
                "Price": parsed["price"],
                "Stock": parsed["status"].value,
                "Website": self.name,
            }
            if parsed["release"] is not None:
                found["Release"] = parsed["release"]

            if found not in all_found:
                all_found.append(found)

        return all_found
