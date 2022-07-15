import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class Game(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = {
            "inStockOnly": "true",
            "pageSize": 100,
            "sortBy": "RELEASE_DATE_DESC",
        }

    base_url = "https://www.game.co.uk/en/amiibo/"
    name = "Game UK"

    def get_amiibo(self):
        all_found = []

        response = self.scrape(url=self.base_url, payload=self.params)
        soup = BeautifulSoup(response.content, "html.parser")
        cards = soup.find_all("article", class_="product")

        if len(cards) == 0:
            log.info("Requests library failed, attempting with selenium")
            response = self.scrape_with_selenium(url=self.base_url, payload=self.params)
            soup = BeautifulSoup(response, "html.parser")
            cards = soup.find_all("article", class_="product")

        for card in cards:
            name = card.find_all("a")
            price = card.find_all(
                "span", attrs={"class": lambda e: e.startswith("value") if e else False}
            )
            img = card.find_all(
                "img",
                attrs={"class": lambda e: e.startswith("optimisedImg") if e else False},
            )
            if name and price and img:
                name = name[1]
                price = price[0]
                img = img[0]
                url = name
            else:
                continue

            found = {
                "Colour": 0x00FF00,
                "Title": name.text.strip(),
                "Image": img["src"].strip(),
                "URL": f"{url['href'].strip()}",
                "Price": price.text.strip(),
                "Stock": Stock.IN_STOCK.value,
                "Website": self.name,
            }

            all_found.append(found)

        return all_found
