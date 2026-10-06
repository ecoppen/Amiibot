import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)

# bestbuy.ca can take 8 to 10 seconds to answer, well past the default timeout.
SLOW_REQUEST_TIMEOUT = 30

AVAILABILITY_URL = "https://www.bestbuy.ca/ecomm-api/availability/products"
# The availability API wants a postal code; any valid one reports online stock.
AVAILABILITY_POSTAL_CODE = "M5G2C3"
AVAILABILITY_BATCH_SIZE = 100

# Best Buy Canada stores release dates as midnight Pacific time.
_RELEASE_TZ = ZoneInfo("America/Vancouver")

_PURCHASABLE = "purchasable"


def _format_release_date(value: Any) -> str | None:
    """Format a release time in epoch milliseconds, or None unless it is today or later."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        release = datetime.fromtimestamp(value / 1000, _RELEASE_TZ).date()
    except (OverflowError, OSError, ValueError):
        return None
    if release < datetime.now(_RELEASE_TZ).date():
        return None
    return f"{release.day} {release.strftime('%b %Y')}"


class BestbuyCA(Stockist):
    def __init__(self, messengers: list[str]) -> None:
        super().__init__(messengers=messengers)

        self.params = {"categoryid": 306351, "page": 1, "pageSize": 100}

    base_url: str = "https://www.bestbuy.ca/api/v2/json/search"
    name: str = "Bestbuy CA"
    request_timeout = SLOW_REQUEST_TIMEOUT

    def _get_purchasable(self, skus: list[str]) -> dict[str, bool] | None:
        """Look up whether each SKU can be bought online right now.

        The search API does not say whether an item is in stock, so ask the
        availability API. Returns None if it cannot be reached, so the caller
        can fall back to assuming the items are in stock.
        """
        purchasable: dict[str, bool] = {}
        for start in range(0, len(skus), AVAILABILITY_BATCH_SIZE):
            batch = skus[start : start + AVAILABILITY_BATCH_SIZE]
            response = self.scrape(
                url=AVAILABILITY_URL,
                payload={
                    "accept": "application/vnd.bestbuy.standardproduct.v1+json",
                    "accept-language": "en-CA",
                    "locations": "",
                    "postalCode": AVAILABILITY_POSTAL_CODE,
                    "skus": "|".join(batch),
                },
            )
            if not response.content:
                log.warning(f"{self.name}: availability request failed")
                return None
            try:
                data = json.loads(response.content.decode("utf-8"))
                for entry in data["availabilities"]:
                    purchasable[str(entry["sku"])] = bool(
                        entry["shipping"][_PURCHASABLE]
                    )
            except (json.JSONDecodeError, AttributeError, KeyError, TypeError) as e:
                log.warning(f"{self.name}: unreadable availability response: {e!r}")
                return None
        return purchasable

    def get_amiibo(self) -> list[dict[str, Any]]:
        all_found = []

        response = self.scrape(url=self.base_url, payload=self.params)

        if not response.content:
            log.error(f"{self.name}: request failed or returned nothing")
            return all_found

        try:
            cards = json.loads(response.content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            log.error(f"Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}")
            return all_found
        except AttributeError as e:
            log.error(f"Invalid attribute: {e}")
            return all_found

        products = cards.get("products") if isinstance(cards, dict) else None
        if not products:
            return all_found

        skus = [str(card["sku"]) for card in products if card.get("sku")]
        purchasable = self._get_purchasable(skus) if skus else None
        if purchasable is None:
            log.warning(
                f"{self.name}: stock levels unavailable, assuming listed items "
                "are in stock"
            )

        for card in products:
            # Convert price to string with currency symbol
            price_value = card["salePrice"]
            price = (
                f"${price_value:.2f}"
                if isinstance(price_value, (int, float))
                else str(price_value)
            )

            preorderable = bool(card.get("isPreorderable"))
            can_buy = (
                purchasable.get(str(card.get("sku")), True)
                if purchasable is not None
                else True
            )

            if not can_buy:
                status, colour = Stock.OUT_OF_STOCK, 0xFF0000
            elif preorderable:
                status, colour = Stock.PRE_ORDER, 0xFFA500
            else:
                status, colour = Stock.IN_STOCK, 0x00FF00

            found = {
                "Colour": colour,
                "Title": card["name"].strip(),
                "Image": card["thumbnailImage"].strip(),
                "URL": f"https://www.bestbuy.ca{card['productUrl'].strip()}",
                "Price": price,
                "Stock": status.value,
                "Website": self.name,
            }

            if preorderable:
                release = _format_release_date(card.get("preorderReleaseDate"))
                if release is not None:
                    found["Release"] = release

            all_found.append(found)

        return all_found
