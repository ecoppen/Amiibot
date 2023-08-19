import logging

import requests  # type: ignore

log = logging.getLogger(__name__)


class Scraper:
    def __init__(self, config, stockists, database) -> None:
        self.stockists = stockists
        self.messengers = stockists.messengers
        self.database = database

    def scrape(self):
        try:
            self.scrape_cycle()
        except requests.exceptions.Timeout:
            log.warning("Request timed out")
        except requests.exceptions.TooManyRedirects:
            log.warning("Too many redirects")
        except requests.exceptions.RequestException as e:
            log.warning(f"Request exception: {e}")

    def scrape_cycle(self):
        for stockist in self.stockists.all_stockists:
            log.info(f"Scraping {stockist.name}")
            scraped = stockist.get_amiibo()
            self.database.update_or_insert_last_scraped(stockist=stockist.name)
            log.info(f"Scraped {len(scraped)} items")
            if len(scraped) > 0:
                to_notify = self.database.check_then_add_or_update_amiibo(scraped)
                if len(to_notify) == 0:
                    continue

                for each in self.messengers.all_messengers:
                    if each.name in stockist.messengers:
                        for item in to_notify:
                            each.send_embed_message(item)
            else:
                log.info(f"{stockist.name} has no amiibo ;(")
