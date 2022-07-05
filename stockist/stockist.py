import logging
import time
from enum import Enum

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from stockist.utils import send_public_request

log = logging.getLogger(__name__)


class Stock(Enum):
    IN_STOCK = "In stock"
    OUT_OF_STOCK = "Out of Stock"


class Stockist:
    def __init__(self):
        self.params = {}

    base_url = None
    name = None

    def scrape(self, url, payload):
        return send_public_request(url=url, payload=payload)

    def scrape_with_selenium(self, url, payload):
        chromedriver_autoinstaller.install()

        options = Options()
        options.headless = True
        options.add_argument("start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(5)
        html = driver.page_source
        driver.quit()
        return html

    def get_amiibo(self):
        pass
