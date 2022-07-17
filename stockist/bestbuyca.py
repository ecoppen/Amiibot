import json
import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class BestbuyCA(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = {"categoryid": 306351, "page": 1, "pageSize": 100}

    base_url = "https://www.bestbuy.ca/api/v2/json/search"
    name = "Bestbuy CA"

    def get_amiibo(self):
        all_found = []

        response = self.scrape(url=self.base_url, payload=self.params)

        try:
            cards = json.loads(response.content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            log.error(f"Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}")
            return all_found

        if "products" in cards:
            for card in cards["products"]:

                found = {
                    "Colour": 0x00FF00,
                    "Title": card["name"].strip(),
                    "Image": card["thumbnailImage"].strip(),
                    "URL": f"https://www.bestbuy.ca{card['productUrl'].strip()}",
                    "Price": card["salePrice"],
                    "Stock": Stock.IN_STOCK.value,
                    "Website": self.name,
                }

                all_found.append(found)

        return all_found
