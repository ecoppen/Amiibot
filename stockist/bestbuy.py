import logging

from bs4 import BeautifulSoup

from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class Bestbuy(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

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
            header = card.find_all(
                "h4",
                attrs={"class": lambda e: e.startswith("sku-title") if e else False},
            )
            if header:
                name = header[0].find_all("a")
            else:
                continue

            stock = card.find_all(
                "button",
                attrs={"class": lambda e: e.startswith("c-button") if e else False},
            )

            price = card.find_all(
                "div",
                attrs={
                    "class": lambda e: (
                        e.startswith("priceView-hero-price") if e else False
                    )
                },
            )

            img = card.find_all(
                "img",
                attrs={
                    "class": lambda e: e.startswith("product-image") if e else False
                },
            )
            if name and stock and price and img:
                name = name[0]
                stock = stock[0]
                price = price[0].find("span")
                img = img[0]
                url = name
            else:
                continue

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
