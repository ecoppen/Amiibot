import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class BestbuyCA(Stockist):
    def __init__(self):
        super().__init__()

        self.params = None

    base_url = "https://www.bestbuy.ca/en-ca/category/nintendo-amiibo/306351"
    name = "Bestbuy CA"

    def get_amiibo(self):
        all_found = []

        response = self.scrape_with_selenium(url=self.base_url, payload=self.params)
        soup = BeautifulSoup(response, "html.parser")
        cards = soup.find_all("div", class_="x-productListItem")

        for card in cards:
            name = card.find_all(
                "div",
                attrs={
                    "class": lambda e: e.startswith("productItemName") if e else False
                },
            )
            stock = card.find_all(
                "span",
                attrs={"class": lambda e: e.startswith("container_") if e else False},
            )
            price = card.find_all(
                "div", attrs={"class": lambda e: e.startswith("price_") if e else False}
            )
            img = card.find_all(
                "img",
                attrs={
                    "class": lambda e: e.startswith("productItemImage") if e else False
                },
            )
            url = card.find_all(
                "a", attrs={"class": lambda e: e.startswith("link_") if e else False}
            )
            if name and stock and price and img and url:
                name = name[0]
                stock = stock[0]
                price = price[0].find("div")
                img = img[0]
                url = url[0]
            else:
                continue
            found = {
                "Colour": 0x0000FF,
                "Title": name.text.strip(),
                "Image": img["src"].strip(),
                "URL": f"https://www.bestbuy.ca/{url['href'].strip()}",
                "Price": price.text.strip(),
                "Stock": "",
                "Website": self.name,
            }

            if stock.text.strip() == "Available to ship":
                found["Colour"] = 0x00FF00
                found["Stock"] = Stock.IN_STOCK.value
            else:
                found["Colour"] = 0xFF0000
                found["Stock"] = Stock.OUT_OF_STOCK.value
            all_found.append(found)

        return all_found
