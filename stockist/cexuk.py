import json
import logging


from stockist.stockist import Stock, Stockist

log = logging.getLogger(__name__)


class CexUK(Stockist):
    def __init__(self, messengers):
        super().__init__(messengers=messengers)

        self.params = {
            "q": "amiibo figures",
            "firstRecord": 1,
            "count": 50,
            "inStock": 1,
            "categoryId": 997,
        }

    base_url = "https://wss2.cex.uk.webuy.io/v3/boxes"
    name = "CeX UK"

    def get_amiibo(self):
        all_found = []
        self.params["firstRecord"] = 1

        switch_params = [
            {"q": "amiibo figures", "categoryId": 997},
            {"q": "amiibo cards", "categoryId": 1104},
        ]
        for categories in switch_params:
            self.params["q"] = categories["q"]
            self.params["categoryId"] = categories["categoryId"]
            for first_record in range(1, 1000, self.params["count"]):
                self.params["firstRecord"] = first_record

                response = self.scrape(url=self.base_url, payload=self.params)

                try:
                    cards = json.loads(response.content.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    log.error(
                        f"Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}"
                    )
                    return all_found
                except AttributeError as e:
                    log.error(f"Invalid attribute: {e}")
                    return all_found

                if "response" in cards:
                    if "data" in cards["response"]:
                        if cards["response"]["data"] is None:
                            break
                        if "boxes" in cards["response"]["data"]:
                            for card in cards["response"]["data"]["boxes"]:
                                found = {
                                    "Colour": 0x00FF00,
                                    "Title": card["boxName"].strip(),
                                    "Image": card["imageUrls"]["medium"].strip(),
                                    "URL": f"https://uk.webuy.com/product-detail/?id={card['boxId']}",
                                    "Price": f"£{card['sellPrice']}",
                                    "Stock": Stock.IN_STOCK.value,
                                    "Website": self.name,
                                }

                                all_found.append(found)
                        else:
                            break
                    else:
                        break
                else:
                    break

        return all_found
