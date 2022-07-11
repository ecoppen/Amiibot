import logging
from typing import Union

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


class StockistManager:
    def __init__(self, messengers) -> None:
        self.all_stockists: list[
            Union[
                Bestbuy,
                BestbuyCA,
                CexUK,
                Game,
                Gamestop,
                MecchaJapan,
                NintendoUK,
                PlayAsia,
                Shopto,
                TheSource,
            ]
        ] = []
        self.messengers = messengers
        self.relationships: dict[str, list[str]] = {}

        for messenger in messengers.all_messengers:
            for stockist in messenger.stockists:
                if stockist not in self.relationships:
                    self.relationships[stockist] = []
                if messenger.name not in self.relationships[stockist]:
                    self.relationships[stockist].append(messenger.name)

        for stockist in self.relationships:
            messengers = self.relationships[stockist]
            if stockist == "bestbuy.com":
                bestbuy = Bestbuy(messengers=messengers)
                self.all_stockists.append(bestbuy)
                log.info(f"Now tracking {stockist}")
            elif stockist == "bestbuy.ca":
                bestbuyca = BestbuyCA(messengers=messengers)
                self.all_stockists.append(bestbuyca)
                log.info(f"Now tracking {stockist}")
            elif stockist == "gamestop.com":
                gamestop = Gamestop(messengers=messengers)
                self.all_stockists.append(gamestop)
                log.info(f"Now tracking {stockist}")
            elif stockist == "game.co.uk":
                game = Game(messengers=messengers)
                self.all_stockists.append(game)
                log.info(f"Now tracking {stockist}")
            elif stockist == "mecca-japan.com":
                meccajapan = MecchaJapan(messengers=messengers)
                self.all_stockists.append(meccajapan)
                log.info(f"Now tracking {stockist}")
            elif stockist == "nintendo.co.uk":
                nintendouk = NintendoUK(messengers=messengers)
                self.all_stockists.append(nintendouk)
                log.info(f"Now tracking {stockist}")
            elif stockist == "play-asia.com":
                playasia = PlayAsia(messengers=messengers)
                self.all_stockists.append(playasia)
                log.info(f"Now tracking {stockist}")
            elif stockist == "shopto.net":
                shopto = Shopto(messengers=messengers)
                self.all_stockists.append(shopto)
                log.info(f"Now tracking {stockist}")
            elif stockist == "thesource.ca":
                thesource = TheSource(messengers=messengers)
                self.all_stockists.append(thesource)
                log.info(f"Now tracking {stockist}")
            elif stockist == "uk.webuy.com":
                cexuk = CexUK(messengers=messengers)
                self.all_stockists.append(cexuk)
                log.info(f"Now tracking {stockist}")

        stockist_check = self.check_for_one_stockist()
        if stockist_check:
            stockists = ", ".join([stockist.name for stockist in self.all_stockists])
            self.messengers.send_message_to_all_messengers(
                f"Now tracking {len(self.all_stockists)} sites: {stockists}"
            )

    def check_for_one_stockist(self):
        if len(self.all_stockists) < 1:
            log.error("No stockists were set to be scraped")
            return False
        return True
