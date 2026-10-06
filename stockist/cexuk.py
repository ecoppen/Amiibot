import json
import logging
from typing import Any
from urllib.parse import urlencode

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)

# CeX's website searches its catalogue through Algolia. These are the public,
# search-only credentials that ship in the website's own JavaScript, so they
# are not secret. CeX may rotate them at any time; if every run starts failing
# with a 401 or 403, copy the new values from the uk.webuy.com network traffic.
ALGOLIA_URL = "https://search.webuy.io/1/indexes/*/queries"
ALGOLIA_API_KEY = "bf79f2b6699e60a18ae330a1248b452c"
ALGOLIA_APP_ID = "LNNFEEWZVA"
ALGOLIA_AGENT = "Algolia for JavaScript (5.52.1); Search (5.52.1); Browser"
ALGOLIA_INDEX = "prod_cex_uk"

REQUEST_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://uk.webuy.com",
    "Referer": "https://uk.webuy.com/",
    # Algolia accepts text/plain, which avoids a CORS preflight in a browser.
    "Content-Type": "text/plain",
}

# `categoryFriendlyName` works; filtering on `categoryId` returns nothing.
BASE_FILTERS = (
    "categoryFriendlyName:Amiibo AND boxVisibilityOnWeb=1 "
    "AND boxSaleAllowed=1 AND sellPrice > 0"
)
ATTRIBUTES = ["boxId", "boxName", "sellPrice", "imageUrls", "ecomQuantity"]

HITS_PER_PAGE = 1000
# Algolia only ever lets a query reach its first 1000 hits, across all pages
# (its default `paginationLimitedTo`). A query that matches this many or more
# can't be listed in full.
MAX_RETRIEVABLE_HITS = 1000
# A safety stop for the paging loop.
MAX_PAGES = 20

PRODUCT_URL = "https://uk.webuy.com/product-detail?id={box_id}"

_NO_STOCK_FILTER = ""
_IN_STOCK_FILTER = " AND inStockOnline=1"
_OUT_OF_STOCK_FILTER = " AND inStockOnline=0"


class CexUK(Stockist):
    def __init__(self, messengers: list[str]) -> None:
        super().__init__(messengers=messengers)

        # The query string of every search request.
        self.params = {
            "x-algolia-agent": ALGOLIA_AGENT,
            "x-algolia-api-key": ALGOLIA_API_KEY,
            "x-algolia-application-id": ALGOLIA_APP_ID,
        }

    base_url: str = ALGOLIA_URL
    name: str = "CeX UK"

    def _search(self, stock_filter: str, page: int) -> dict[str, Any] | None:
        """Run one search request; None if it failed or the answer is unusable."""
        search_params = {
            "query": "",
            "hitsPerPage": HITS_PER_PAGE,
            "page": page,
            "filters": BASE_FILTERS + stock_filter,
            "attributesToRetrieve": json.dumps(ATTRIBUTES),
        }
        body = {
            "requests": [
                {"indexName": ALGOLIA_INDEX, "params": urlencode(search_params)}
            ]
        }

        response = self.post(
            url=self.base_url,
            params=self.params,
            data=json.dumps(body),
            headers=REQUEST_HEADERS,
        )

        if not getattr(response, "content", None):
            status = getattr(response, "status_code", None)
            if status in (401, 403):
                log.error(
                    f"{self.name}: the search service refused the request "
                    f"(HTTP {status}). CeX's public search key in "
                    "stockist/cexuk.py may have changed."
                )
            else:
                log.error(f"{self.name}: request failed or returned nothing")
            return None

        try:
            result = json.loads(response.content.decode("utf-8"))["results"][0]
            result["hits"] = list(result["hits"])
            result["nbHits"] = int(result["nbHits"])
            result["nbPages"] = int(result["nbPages"])
        except json.JSONDecodeError as exc:
            log.error(f"Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}")
            return None
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
            log.error(f"{self.name}: unexpected search response: {e!r}")
            return None
        return result

    def _fetch(self, stock_filter: str) -> tuple[list[dict[str, Any]], int] | None:
        """Fetch every page of one query. Returns (hits, nbHits), or None on failure.

        Stops early once nbHits reaches the retrievable limit, since the caller
        can't use a truncated list anyway.
        """
        hits: list[dict[str, Any]] = []
        page = 0
        while True:
            result = self._search(stock_filter, page)
            if result is None:
                return None
            hits.extend(result["hits"])
            if result["nbHits"] >= MAX_RETRIEVABLE_HITS:
                return hits, result["nbHits"]
            page += 1
            if page >= result["nbPages"] or page >= MAX_PAGES:
                return hits, result["nbHits"]

    def _list_all(self) -> list[dict[str, Any]] | None:
        """Every amiibo hit, or None if the full list could not be fetched.

        Returning a partial list would make the missing items look delisted,
        so a failure or an over-large result gives None rather than less.
        """
        everything = self._fetch(_NO_STOCK_FILTER)
        if everything is None:
            return None
        hits, total = everything
        if total < MAX_RETRIEVABLE_HITS:
            return hits

        log.warning(
            f"{self.name}: {total} products match, which is more than a single "
            f"search can list ({MAX_RETRIEVABLE_HITS}); splitting by stock"
        )
        hits = []
        for stock_filter in (_IN_STOCK_FILTER, _OUT_OF_STOCK_FILTER):
            subset = self._fetch(stock_filter)
            if subset is None:
                return None
            subset_hits, subset_total = subset
            if subset_total >= MAX_RETRIEVABLE_HITS:
                log.warning(
                    f"{self.name}: {subset_total} products match even after "
                    "splitting by stock, so the list would be incomplete; "
                    "treating the run as failed instead of risking false delistings"
                )
                return None
            hits.extend(subset_hits)
        return hits

    @staticmethod
    def _image_url(image_urls: Any) -> str:
        if not isinstance(image_urls, dict):
            return ""
        for key in ("medium", "large"):
            value = image_urls.get(key)
            if isinstance(value, str) and value.strip():
                url = value.strip()
                if url.startswith("//"):
                    return f"https:{url}"
                if url.startswith("http://"):
                    return f"https://{url[len('http://') :]}"
                return url
        return ""

    def get_amiibo(self) -> list[dict[str, Any]]:
        hits = self._list_all()
        if hits is None:
            return []

        all_found: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            try:
                box_id = str(hit["boxId"]).strip()
                title = str(hit["boxName"]).strip()
                price = f"£{float(hit['sellPrice']):.2f}"
            except (KeyError, TypeError, ValueError):
                log.debug(f"{self.name}: skipping unreadable hit {hit!r}")
                continue
            if not box_id or not title or box_id in seen:
                continue
            seen.add(box_id)

            quantity = hit.get("ecomQuantity")
            in_stock = (
                isinstance(quantity, (int, float))
                and not isinstance(quantity, bool)
                and quantity > 0
            )
            status = Stock.IN_STOCK if in_stock else Stock.OUT_OF_STOCK

            all_found.append(
                {
                    "Colour": 0x00FF00 if in_stock else 0xFF0000,
                    "Title": title,
                    "Image": self._image_url(hit.get("imageUrls")),
                    "URL": PRODUCT_URL.format(box_id=box_id),
                    "Price": price,
                    "Stock": status.value,
                    "Website": self.name,
                }
            )

        return all_found
