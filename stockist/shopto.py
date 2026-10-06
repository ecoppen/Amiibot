import logging
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

from stockist.stockist import Stock, Stockist
from stockist.utils import attr_text

log = logging.getLogger(__name__)


class Shopto(Stockist):
    def __init__(self, messengers: list[str]) -> None:
        super().__init__(messengers=messengers)

        self.params = None

    base_url: str = "https://www.shopto.net/en/search/?input_search=amiibo"
    name: str = "Shopto"

    def get_amiibo(self) -> list[dict[str, Any]]:
        all_found: list[dict[str, Any]] = []

        response = self.scrape(url=self.base_url, payload=self.params)
        soup = BeautifulSoup(response.content, "html.parser")
        cards = soup.find_all("div", class_="itemlist2")

        if len(cards) == 0:
            log.info("Requests library failed, attempting with selenium")
            response = self.scrape_with_selenium(url=self.base_url, payload=self.params)
            soup = BeautifulSoup(response, "html.parser")
            cards = soup.find_all("div", class_="itemlist2")

        for card in cards:
            if not isinstance(card, Tag):
                continue

            name = card.find_all(
                "div",
                attrs={
                    "class": lambda e: (
                        e.startswith("itemlist__description") if e else False
                    )
                },
            )
            stock = card.find_all(
                "div",
                attrs={"class": lambda e: e.startswith("inventory") if e else False},
            )
            price = card.find_all(
                "div",
                attrs={"class": lambda e: e.startswith("cross_price") if e else False},
            )
            img = card.find_all("img")
            url = card.find_all(
                "a",
                attrs={
                    "class": lambda e: (
                        e.startswith("itemlist__container") if e else False
                    )
                },
            )

            if not (name and stock and price and img and url):
                continue

            found = {
                "Colour": 0x0000FF,
                "Title": name[0].text.strip(),
                "Image": f"https://www.shopto.net{attr_text(img[0], 'src')}",
                "URL": f"https://www.shopto.net{attr_text(url[0], 'href')}",
                "Price": price[0].text.strip(),
                "Stock": "",
                "Website": self.name,
            }

            if stock[0].text.strip() == "Sold out":
                found["Colour"] = 0xFF0000
                found["Stock"] = Stock.OUT_OF_STOCK.value
            else:
                found["Colour"] = 0x00FF00
                found["Stock"] = Stock.IN_STOCK.value
            all_found.append(found)

        return all_found
