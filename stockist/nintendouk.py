import json
import logging

import requests  # type: ignore
from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class NintendoUK(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = {
            "checkAvailability": "true",
            "limit": 24,
            "sort": "newest-products",
            "refine": '["cgid=amiibo"]',
            "offset": 0,
        }

    base_url = "https://store.nintendo.co.uk/api/catalog/products"
    name = "Nintendo UK"

    def get_amiibo(self):
        all_found = []
        complete = False

        while not complete:
            response = self.scrape(url=self.base_url, payload=self.params)

            try:
                cards = json.loads(response.content.decode("utf-8"))
            except json.JSONDecodeError as exc:
                log.error(
                    f"Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}"
                )
                cards = []
            except AttributeError as e:
                log.error(f"Invalid attribute: {e}")
                cards = []

            if len(cards) > 0:
                if "data" in [*cards]:
                    if "products" in [*cards["data"]]:
                        if len(cards["data"]["products"]) == 0:
                            complete = True
                        for card in cards["data"]["products"]:
                            name = card["name"]
                            price = card["pricePerUnit"]
                            img = card["c_productImages"][0]
                            url = card["path"]
                            stock = card["c_availabilityModel"]["type"]

                            found = {
                                "Colour": 0x0000FF,
                                "Title": name,
                                "Image": f"https://assets.nintendo.eu/image/upload/v1654696477/{img}",
                                "URL": f"https://store.nintendo.co.uk{url}",
                                "Price": price,
                                "Stock": "",
                                "Website": self.name,
                            }

                            if stock == "OutOfStock":
                                found["Colour"] = 0xFF0000
                                found["Stock"] = Stock.OUT_OF_STOCK.value
                            else:
                                found["Colour"] = 0x00FF00
                                found["Stock"] = Stock.IN_STOCK.value

                            if found not in all_found:
                                all_found.append(found)
                        self.params["offset"] += 24
                        if self.params["offset"] > 500:
                            break
            else:
                break
        if len(all_found) == 0:
            log.info("Requests library failed, attempting with selenium")
            self.base_url = (
                "https://store.nintendo.co.uk/en_gb/games/enhance-your-play/amiibo/"
            )

            response = self.scrape_with_selenium(url=self.base_url, payload=self.params)
            soup = BeautifulSoup(response, "html.parser")
            cards = soup.find_all(
                "div",
                attrs={"class": lambda e: e.startswith("col-6") if e else False},
            )

            for card in cards:
                name = card.find_all(
                    "h3",
                    attrs={
                        "class": lambda e: e.startswith("ProductCard_card__title")
                        if e
                        else False
                    },
                )
                stock = card.find_all(
                    "button",
                    attrs={
                        "class": lambda e: e.startswith("ProductCard_btn")
                        if e
                        else False
                    },
                )
                price = card.find_all(
                    "data",
                    attrs={"class": lambda e: e.startswith("value") if e else False},
                )
                img = card.find_all("img")
                url = card.find_all(
                    "a",
                    attrs={
                        "class": lambda e: e.startswith("ProductCard_card__link")
                        if e
                        else False
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
                    "URL": f"https://store.nintendo.co.uk/{url['href'].strip()}",
                    "Price": price.text.strip(),
                    "Stock": "",
                    "Website": self.name,
                }

                if 'disabled=""' in str(stock):
                    found["Colour"] = 0xFF0000
                    found["Stock"] = Stock.OUT_OF_STOCK.value
                else:
                    found["Colour"] = 0x00FF00
                    found["Stock"] = Stock.IN_STOCK.value

                if found not in all_found:
                    all_found.append(found)
        return all_found
