import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class NintendoUK(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

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
                name = card.find_all(
                    "h2",
                    attrs={
                        "class": lambda e: e.startswith("card__title") if e else False
                    },
                )
                stock = card.find_all(
                    "span",
                    attrs={
                        "class": lambda e: e.startswith("btn__text") if e else False
                    },
                )
                price = card.find_all(
                    "data",
                    attrs={"class": lambda e: e.startswith("value") if e else False},
                )
                img = card.find_all(
                    "img",
                    attrs={
                        "class": lambda e: e.startswith("tile-image") if e else False
                    },
                )
                url = card.find_all(
                    "a",
                    attrs={
                        "class": lambda e: e.startswith("card__link") if e else False
                    },
                )

                if name and stock and price and img and url:
                    name = name[0]
                    stock = stock[0]
                    price = price[0]
                    img = img[0]
                    url = url[0]
                else:
                    continue

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
