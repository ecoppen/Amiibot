import json
import logging


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
        self.params["offset"] = 0

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
                    log.debug(f'{cards["data"]}')
                    if cards["data"] is None:
                        log.warning("No data returned from API")
                        break
                    if "products" in cards["data"]:
                        log.debug(f'{cards["data"]["products"]}')
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
        return all_found
