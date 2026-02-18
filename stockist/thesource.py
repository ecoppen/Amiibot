import logging

from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class TheSource(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = None

    base_url = "https://www.thesource.ca/en-ca/search?q=amiibo&page="
    name = "The Source"

    def get_amiibo(self):
        options = range(0, 2)

        all_found = []

        for each in options:
            response = self.scrape(url=f"{self.base_url}{each}", payload=self.params)

            soup = BeautifulSoup(response.content, "html.parser")
            cards = soup.find_all("div", class_="productListItem")

            if len(cards) == 0:
                log.info("Requests library failed, attempting with selenium")
                response = self.scrape_with_selenium(
                    url=self.base_url, payload=self.params
                )
                soup = BeautifulSoup(response, "html.parser")
                cards = soup.find_all("div", class_="productListItem")

            for card in cards:
                name = card.find_all(
                    "div",
                    attrs={
                        "class": lambda e: (
                            e.startswith("productMainLink") if e else False
                        )
                    },
                )
                if name:
                    name = card.find_all("span")
                else:
                    continue

                stock = card.find_all("button")
                price = card.find_all(
                    "div",
                    attrs={
                        "class": lambda e: e.startswith("sale-price") if e else False
                    },
                )
                img = card.find_all(
                    "img",
                    attrs={
                        "class": lambda e: e.startswith("primary-image") if e else False
                    },
                )
                url = card.find_all("a")

                if name and price and stock and img and url:
                    name = name[0]
                    price = price[0]
                    stock = stock[0]
                    img = img[0]
                    url = url[0]
                else:
                    continue

                found = {
                    "Colour": 0x0000FF,
                    "Title": name.text.strip(),
                    "Image": f"https://www.thesource.ca/{img['src'].strip()}",
                    "URL": f"https://www.thesource.ca/{url['href'].strip()}",
                    "Price": price.text.strip(),
                    "Stock": "",
                    "Website": self.name,
                }

                if stock.text.strip() == "Add to Cart":
                    found["Colour"] = 0x00FF00
                    found["Stock"] = Stock.IN_STOCK.value
                else:
                    found["Colour"] = 0xFF0000
                    found["Stock"] = Stock.OUT_OF_STOCK.value

                all_found.append(found)
        return all_found
