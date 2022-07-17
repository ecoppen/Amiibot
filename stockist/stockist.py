import logging
import secrets
import time
from enum import Enum
from typing import Any, Union

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options

from stockist.useragents import UserAgent
from stockist.utils import send_public_request

log = logging.getLogger(__name__)

user_agents = UserAgent()
user_agent_list = user_agents.get_user_agents()


class Stock(Enum):
    DELISTED = "Delisted"
    IN_STOCK = "In stock"
    OUT_OF_STOCK = "Out of Stock"
    PRICE_CHANGE = "Price change"


class Stockist:
    def __init__(self, messengers) -> None:
        self.params: dict[str, Any] = {}
        self.messengers = messengers

    base_url: Union[str, None] = None
    name: Union[str, None] = None

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
        options.add_argument("--no-sandbox")
        options.add_argument(f"user-agent={secrets.choice(user_agent_list)}")
        try:
            driver = webdriver.Chrome(options=options)
            driver.get(url)
        except WebDriverException as e:
            log.error(f"Selenium exception: {e.msg}")
            return ""
        time.sleep(5)
        html = driver.page_source
        driver.quit()
        return html

    def get_amiibo(self):
        pass
