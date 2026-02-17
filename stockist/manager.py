import logging
from typing import Any

from stockist.bestbuy import Bestbuy
from stockist.bestbuyca import BestbuyCA
from stockist.cexuk import CexUK
from stockist.game import Game
from stockist.gamestop import Gamestop
from stockist.mecchajapan import MecchaJapan
from stockist.nintendouk import NintendoUK
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto
from stockist.thesource import TheSource

log = logging.getLogger(__name__)

# Stockist factory mapping
STOCKIST_FACTORY = {
    "bestbuy.com": Bestbuy,
    "bestbuy.ca": BestbuyCA,
    "gamestop.com": Gamestop,
    "game.co.uk": Game,
    "meccha-japan.com": MecchaJapan,
    "nintendo.co.uk": NintendoUK,
    "play-asia.com": PlayAsia,
    "shopto.net": Shopto,
    "thesource.ca": TheSource,
    "uk.webuy.com": CexUK,
}


class StockistManager:
    def __init__(self, messengers: Any) -> None:
        self.all_stockists: list[Any] = []
        self.messengers = messengers
        self.relationships: dict[str, list[str]] = {}

        # Build relationships between messengers and stockists
        for messenger in messengers.all_messengers:
            for stockist in messenger.stockists:
                if stockist not in self.relationships:
                    self.relationships[stockist] = []
                if messenger.name not in self.relationships[stockist]:
                    self.relationships[stockist].append(messenger.name)

        # Instantiate stockists using factory
        for stockist_url, messenger_names in self.relationships.items():
            if stockist_url not in STOCKIST_FACTORY:
                log.warning(f"Unknown stockist URL: {stockist_url}. Skipping.")
                continue

            stockist_class = STOCKIST_FACTORY[stockist_url]
            try:
                stockist_instance = stockist_class(messengers=messenger_names)
                self.all_stockists.append(stockist_instance)
                log.info(f"Now tracking {stockist_url}")
            except Exception as e:
                log.error(f"Failed to instantiate stockist {stockist_url}: {e}")

        self._validate_stockists()

    def _validate_stockists(self) -> bool:
        """Validate that at least one stockist was initialized."""
        if len(self.all_stockists) < 1:
            log.error("No stockists were set to be scraped")
            return False

        stockist_names = ", ".join([stockist.name for stockist in self.all_stockists])
        log.info(f"Now scraping {len(self.all_stockists)} site(s): {stockist_names}")
        return True
