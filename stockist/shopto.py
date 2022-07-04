import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class Shopto(Stockist):
    def __init__(self):
        super().__init__()

        self.params = None

    base_url = "https://www.shopto.net/en/nintendo-amiibo/"
    name = "Shopto"

    def get_amiibo(self):
        all_found = []

        response = self.scrape(url=self.base_url, payload=self.params)
        soup = BeautifulSoup(response.content, "html.parser")
        cards = soup.find_all("div", class_="itemlist2")

        if len(cards) == 0:
            log.info("Requests library failed, attempting with selenium")
            response = self.scrape_with_selenium(url=self.base_url, payload=self.params)
            soup = BeautifulSoup(response, "html.parser")
            cards = soup.find_all("div", class_="itemlist2")

        for card in cards:
            name = card.find("div", class_="itemlist__description")
            stock = card.find("div", class_="inventory")
            price = card.find("div", class_="cross_price")
            img = card.find("div", class_="image")
            img = img.find("img")
            url = card.find("a", class_="itemlist__container")

            found = {
                "Colour": 0x0000FF,
                "Title": name.text.strip(),
                "Image": f"https://www.shopto.net/{img['src'].strip()}",
                "URL": f"https://www.shopto.net/{url['href'].strip()}",
                "Price": price.text.strip(),
                "Stock": "",
                "Website": self.name,
            }

            if stock.text.strip() == "Sold out":
                found["Colour"] = 0xFF0000
                found["Stock"] = Stock.OUT_OF_STOCK.value
            else:
                found["Colour"] = 0x00FF00
                found["Stock"] = Stock.IN_STOCK.value
            all_found.append(found)

        return all_found
