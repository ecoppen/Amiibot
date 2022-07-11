import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class MecchaJapan(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = None

    base_url = "https://meccha-japan.com/en/367-amiibo?page="
    name = "Meccha Japan"

    def get_amiibo(self):
        options = range(1, 5)

        all_found = []

        for each in options:
            response = self.scrape(url=f"{self.base_url}{each}", payload=self.params)

            soup = BeautifulSoup(response.content, "html.parser")
            cards = soup.find_all("article", class_="product-miniature")

            if len(cards) == 0:
                log.info("Requests library failed, attempting with selenium")
                response = self.scrape_with_selenium(
                    url=self.base_url, payload=self.params
                )
                soup = BeautifulSoup(response, "html.parser")
                cards = soup.find_all("article", class_="product-miniature")

            for card in cards:
                header = card.find_all(
                    "h2",
                    attrs={
                        "class": lambda e: e.startswith("product-title") if e else False
                    },
                )
                if header:
                    name = header[0].find_all("a")
                else:
                    continue

                price = card.find_all(
                    "span",
                    attrs={"class": lambda e: e.startswith("price") if e else False},
                )
                img = card.find_all("img")
                url = card.find_all("a")
                oos = card.find_all(
                    "div",
                    attrs={
                        "class": lambda e: e.startswith("oos-label") if e else False
                    },
                )

                if name and price and img and url and not oos:
                    name = name[0]
                    price = price[0]
                    img = img[0]
                    url = url[0]
                else:
                    continue

                found = {
                    "Colour": 0x00FF00,
                    "Title": name.text.strip(),
                    "Image": f"{img['src'].strip()}",
                    "URL": f"{url['href'].strip()}",
                    "Price": price.text.strip(),
                    "Stock": Stock.IN_STOCK.value,
                    "Website": self.name,
                }

                all_found.append(found)

        return all_found
