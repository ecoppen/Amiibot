import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class Bestbuy(Stockist):
    def __init__(self):
        super().__init__()

        self.params = None

    base_url = "https://www.bestbuy.com/site/toys-to-life/amiibo/pcmcat385200050004.c?intl=nosplash"
    name = "Bestbuy US"

    def get_amiibo(self):
        all_found = []

        response = self.scrape(url=self.base_url, payload=self.params)

        soup = BeautifulSoup(response.content, "html.parser")
        cards = soup.find_all("li", class_="sku-item")

        if len(cards) == 0:
            log.info("Requests library failed, attempting with selenium")
            response = self.scrape_with_selenium(url=self.base_url, payload=self.params)
            soup = BeautifulSoup(response, "html.parser")
            cards = soup.find_all("li", class_="sku-item")

        for card in cards:
            header = card.find("h4", class_="sku-title")
            name = header.find("a", class_="")
            stock = card.find("button", class_="c-button")
            price = card.find("div", class_="priceView-hero-price")
            price = price.find("span")
            img = card.find("img", class_="product-image")
            url = header.find("a", class_="")

            found = {
                "Colour": 0x0000FF,
                "Title": name.text.strip(),
                "Image": img["src"].strip(),
                "URL": f"https://www.bestbuy.com/{url['href'].strip()}",
                "Price": price.text.strip(),
                "Stock": "",
                "Website": self.name,
            }

            if stock.text.strip() == "Sold Out":
                found["Colour"] = 0xFF0000
                found["Stock"] = Stock.OUT_OF_STOCK.value
            else:
                found["Colour"] = 0x00FF00
                found["Stock"] = Stock.IN_STOCK.value
            all_found.append(found)

        return all_found
