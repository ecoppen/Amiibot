import logging

from stockist.bestbuy import Bestbuy
from stockist.bestbuyca import BestbuyCA
from stockist.game import Game
from stockist.gamestop import Gamestop
from stockist.mecchajapan import MecchaJapan
from stockist.nintendouk import NintendoUK
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto
from stockist.thesource import TheSource

log = logging.getLogger(__name__)


class StockistManager:
    def __init__(self, config, messengers) -> None:
        self.all_stockists = []
        self.messengers = messengers

        for stockist in config:
            if stockist == "bestbuy.com":
                bestbuy = Bestbuy()
                self.all_stockists.append(bestbuy)
                log.info(f"Now tracking {stockist}")
            elif stockist == "bestbuy.ca":
                bestbuyca = BestbuyCA()
                self.all_stockists.append(bestbuyca)
                log.info(f"Now tracking {stockist}")
            elif stockist == "gamestop.com":
                gamestop = Gamestop()
                self.all_stockists.append(gamestop)
                log.info(f"Now tracking {stockist}")
            elif stockist == "game.co.uk":
                game = Game()
                self.all_stockists.append(game)
                log.info(f"Now tracking {stockist}")
            elif stockist == "mecca-japan.com":
                meccajapan = MecchaJapan()
                self.all_stockists.append(meccajapan)
                log.info(f"Now tracking {stockist}")
            elif stockist == "nintendo.co.uk":
                nintendouk = NintendoUK()
                self.all_stockists.append(nintendouk)
                log.info(f"Now tracking {stockist}")
            elif stockist == "play-asia.com":
                playasia = PlayAsia()
                self.all_stockists.append(playasia)
                log.info(f"Now tracking {stockist}")
            elif stockist == "shopto.net":
                shopto = Shopto()
                self.all_stockists.append(shopto)
                log.info(f"Now tracking {stockist}")
            elif stockist == "thesource.ca":
                thesource = TheSource()
                self.all_stockists.append(thesource)
                log.info(f"Now tracking {stockist}")

        stokist_check = self.check_for_one_stockist()
        if stokist_check:
            stockists = ", ".join([stockist.name for stockist in self.all_stockists])
            self.messengers.send_message_to_all_messengers(
                f"Now tracking {len(self.all_stockists)} sites: {stockists}"
            )

    def check_for_one_stockist(self):
        if len(self.all_stockists) < 1:
            log.error("No messengers were set to true")
            return False
        return True
