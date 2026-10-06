import json
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)

# Availability types reported by the Nintendo UK API, mapped to a stock status
# and embed colour. Anything not listed here is treated as out of stock.
_AVAILABILITY: dict[str, tuple[Stock, int]] = {
    "InStock": (Stock.IN_STOCK, 0x00FF00),
    "PreOrder": (Stock.PRE_ORDER, 0xFFA500),
    "OutOfStock": (Stock.OUT_OF_STOCK, 0xFF0000),
}


_UK_TZ = ZoneInfo("Europe/London")


def _format_release_date(value: Any) -> str | None:
    """Format a "YYYY-MM-DD" release date, or None unless it is today or later."""
    if not isinstance(value, str):
        return None
    try:
        release = date.fromisoformat(value.strip())
    except ValueError:
        return None
    # Nintendo UK is a UK store, so "today" is the date in London.
    if release < datetime.now(_UK_TZ).date():
        return None
    return f"{release.day} {release.strftime('%b %Y')}"


class NintendoUK(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = {
            "checkAvailability": "true",
            "limit": 24,
            "sort": "newest-products",
            "refine": '["cgid=amiibo"]',
            "offset": 0,
        }

    base_url = "https://store.nintendo.co.uk/api/catalog/products"
    name = "Nintendo UK"

    def get_amiibo(self):
        all_found = []
        complete = False
        self.params["offset"] = 0

        while not complete:
            response = self.scrape(url=self.base_url, payload=self.params)

            if not response.content:
                log.error(f"{self.name}: request failed or returned nothing")
                break

            try:
                cards = json.loads(response.content.decode("utf-8"))
            except json.JSONDecodeError as exc:
                log.error(
                    f"Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}"
                )
                cards = []
            except AttributeError as e:
                log.error(f"Invalid attribute: {e}")
                cards = []

            if len(cards) > 0:
                if "data" in [*cards]:
                    log.debug(f"{cards['data']}")
                    if cards["data"] is None:
                        log.warning("No data returned from API")
                        break
                    if "products" in cards["data"]:
                        log.debug(f"{cards['data']['products']}")
                        if len(cards["data"]["products"]) == 0:
                            complete = True
                        for card in cards["data"]["products"]:
                            name = card["name"]
                            price_value = card["pricePerUnit"]
                            # Convert float price to string with currency symbol
                            price = (
                                f"£{price_value:.2f}"
                                if isinstance(price_value, (int, float))
                                else str(price_value)
                            )
                            img = card["c_productImages"][0]
                            url = card["path"]
                            stock = card["c_availabilityModel"]["type"]

                            found = {
                                "Colour": 0x0000FF,
                                "Title": name,
                                "Image": f"https://assets.nintendo.eu/image/upload/v1654696477/{img}",
                                "URL": f"https://store.nintendo.co.uk{url}",
                                "Price": price,
                                "Stock": "",
                                "Website": self.name,
                            }

                            if stock in _AVAILABILITY:
                                status, colour = _AVAILABILITY[stock]
                            else:
                                log.warning(
                                    f"Unknown availability type {stock!r} for "
                                    f"{name}; treating as out of stock"
                                )
                                status, colour = _AVAILABILITY["OutOfStock"]
                            found["Colour"] = colour
                            found["Stock"] = status.value

                            release = _format_release_date(card.get("c_releaseDate"))
                            if release is not None:
                                found["Release"] = release

                            if found not in all_found:
                                all_found.append(found)
                        self.params["offset"] += 24
                        if self.params["offset"] > 500:
                            break
            else:
                break
        return all_found
