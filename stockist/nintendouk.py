import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class NintendoUK(Stockist):
    def __init__(self):
        super().__init__()

        self.params = {
            "cgid": "amiibo",
            "start": 0,
            "sz": 100,
            "srule": "newest-products",
        }

    base_url = "https://store.nintendo.co.uk/en_gb/games/enhance-your-play/amiibo/"
    name = "Nintendo UK"

    def get_amiibo(self):
        options = ["newest-products", "price-high-to-low", "price-low-to-high"]

        all_found = []

        for each in options:
            self.params["srule"] = each

            response = self.scrape(url=self.base_url, payload=self.params)

            soup = BeautifulSoup(response.content, "html.parser")
            cards = soup.find_all("div", class_="js-gtm-productImpression-item")

            if len(cards) == 0:
                log.info("Requests library failed, attempting with selenium")
                response = self.scrape_with_selenium(
                    url=self.base_url, payload=self.params
                )
                soup = BeautifulSoup(response, "html.parser")
                cards = soup.find_all("div", class_="js-gtm-productImpression-item")

            for card in cards:
                name = card.find("h2", class_="card__title")
                stock = card.find("span", class_="btn__text")
                price = card.find("data", class_="value")
                img = card.find("img", class_="tile-image")
                url = card.find("a", class_="card__link")

                found = {
                    "Colour": 0x0000FF,
                    "Title": name.text.strip(),
                    "Image": img["src"].strip(),
                    "URL": f"https://store.nintendo.co.uk/en_gb/{url['href'].strip()}",
                    "Price": price.text.strip(),
                    "Stock": "",
                    "Website": self.name,
                }

                if stock.text.strip() == "ADD TO CART":
                    found["Colour"] = 0x00FF00
                    found["Stock"] = Stock.IN_STOCK.value
                else:
                    found["Colour"] = 0xFF0000
                    found["Stock"] = Stock.OUT_OF_STOCK.value
                all_found.append(found)

        return all_found
