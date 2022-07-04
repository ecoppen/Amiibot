import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class Gamestop(Stockist):
    def __init__(self):
        super().__init__()

        self.params = {
            "prefn1": "buryMaster",
            "prefv1": "In Stock"
        }

    base_url = "https://www.gamestop.com/consoles-hardware/nintendo-switch/nintendo-switch-amiibo"
    name = "Gamestop US"

    def get_amiibo(self):
        all_found = []

        response = self.scrape_with_selenium(url=self.base_url, payload=self.params)

        soup = BeautifulSoup(response, "html.parser")
        cards = soup.find_all("div", class_="product grid-tile")

        if len(cards) == 0:
            log.info("Selenium failed, attempting with requests")
            response = self.scrape(
                url=self.base_url, payload=self.params
            )
            soup = BeautifulSoup(response.content, "html.parser")
            cards = soup.find_all("div", class_="product grid-tile")

        for card in cards:
            name = card.find_all("p", attrs={"class": lambda e: e.startswith("pd-name") if e else False})
            price = card.find_all("span", attrs={"class": lambda e: e.startswith("actual-price") if e else False})
            img = card.find_all("img", attrs={"class": lambda e: e.startswith("tile-image") if e else False})
            url = card.find_all("a", attrs={"class": lambda e: e.startswith("product-tile-link") if e else False})

            if name and price and img and url:
                name = name[0]
                price = price[0]
                img = img[0]
                url = url[0]
            else:
                continue
            
            found = {
                "Colour": 0x00FF00,
                "Title": name.text.strip(),
                "Image": img["src"].strip(),
                "URL": f"https://www.gamestop.com{url['href'].strip()}",
                "Price": price.text.strip(),
                "Stock": Stock.IN_STOCK.value,
                "Website": self.name,
            }

            all_found.append(found)

        return all_found
