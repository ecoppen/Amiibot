import logging
import os
from pathlib import Path

from config.config import load_config
from database import Database
from messenger.manager import MessageManager
from scraper import Scraper
from stockist.manager import StockistManager

logs_file = Path(Path().resolve(), "log.txt")
logs_file.touch(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=os.environ.get("LOGLEVEL", "INFO"),
    handlers=[logging.FileHandler(logs_file), logging.StreamHandler()],
)

log = logging.getLogger(__name__)

config_path = Path("config", "config.json")
config = load_config(path=config_path)
log.info(f"{config_path} loaded")

database = Database(config=config.database)
messengers = MessageManager(config=config.messengers)
stockists = StockistManager(messengers=messengers)
scraper = Scraper(config=config, stockists=stockists, database=database)

scraper.scrape()
