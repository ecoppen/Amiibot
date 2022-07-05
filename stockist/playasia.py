import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class PlayAsia(Stockist):
    def __init__(self):
        super().__init__()

        self.params = None

    base_url = "https://www.play-asia.com/games/amiibos/14/712od#fc=s:3,m:6,p:"
    name = "Playasia"

    def get_amiibo(self):
        options = range(1, 11)

        all_found = []

        for each in options:
            response = self.scrape(url=f"{self.base_url}{each}", payload=self.params)

            soup = BeautifulSoup(response.content, "html.parser")
            cards = soup.find_all("div", class_="p_prev")

            if len(cards) == 0:
                log.info("Requests library failed, attempting with selenium")
                response = self.scrape_with_selenium(
                    url=self.base_url, payload=self.params
                )
                soup = BeautifulSoup(response, "html.parser")
                cards = soup.find_all("div", class_="p_prev")

            for card in cards:
                name = card.find_all(
                    "span",
                    attrs={"class": lambda e: e.startswith("p_prev_n") if e else False},
                )
                price = card.find_all(
                    "span",
                    attrs={
                        "class": lambda e: e.startswith("price_val") if e else False
                    },
                )
                img = card.find_all(
                    "img",
                    attrs={
                        "class": lambda e: e.startswith("p_prev_img") if e else False
                    },
                )
                url = card.find_all("a")

                if name and price and img and url:
                    name = name[0]
                    price = price[0].find("div")
                    img = img[0]
                    url = url[0]
                else:
                    continue

                found = {
                    "Colour": 0x00FF00,
                    "Title": name.text.strip(),
                    "Image": f"https:{img['src'].strip()}",
                    "URL": f"https://www.play-asia.com/{url['href'].strip()}",
                    "Price": price.text.strip(),
                    "Stock": Stock.IN_STOCK.value,
                    "Website": self.name,
                }

                all_found.append(found)

        return all_found
