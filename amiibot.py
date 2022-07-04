import logging
import os
import time
from pathlib import Path

from config.config import load_config
from database import Database
from messenger.manager import MessageManager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=os.environ.get("LOGLEVEL", "INFO"),
)

log = logging.getLogger(__name__)

config_path = Path("config", "config.json")
config = load_config(config_path)
log.info(f"{config_path} loaded")

database = Database(config.database)

messengers = MessageManager(config.messengers)

from stockist.bestbuy import Bestbuy
from stockist.bestbuyca import BestbuyCA
from stockist.game import Game
from stockist.nintendouk import NintendoUK
from stockist.playasia import PlayAsia
from stockist.shopto import Shopto

x = PlayAsia()
for each in messengers.all_messengers:
    for item in x.get_amiibo():
        response = each.send_embed_message(embed_data=item)
        time.sleep(0.5)
