import logging
import secrets
import time
import urllib.error
from enum import Enum
from typing import Any, Optional

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options

from constants import SELENIUM_WAIT_TIME, FALLBACK_USER_AGENTS
from stockist.useragents import UserAgent
from stockist.utils import send_public_request

log = logging.getLogger(__name__)

user_agents = UserAgent()
user_agent_list = user_agents.get_user_agents()

# Validate user agent list is not empty
if not user_agent_list:
    log.error("User agent list is empty! Using fallback agents.")
    user_agent_list = FALLBACK_USER_AGENTS


class Stock(Enum):
    """Stock status enumeration."""

    DELISTED = "Delisted"
    IN_STOCK = "In stock"
    OUT_OF_STOCK = "Out of Stock"
    PRICE_CHANGE = "Price change"


class Stockist:
    """Base class for all stockist scrapers."""

    def __init__(self, messengers: list[str]) -> None:
        """Initialize stockist.

        Args:
            messengers: List of messenger names to notify
        """
        self.params: dict[str, Any] = {}
        self.messengers = messengers

    base_url: Optional[str] = None
    name: Optional[str] = None

    def scrape(self, url: str, payload: Optional[dict[str, Any]]) -> Any:
        """Scrape a URL using requests library.

        Args:
            url: URL to scrape
            payload: Query parameters

        Returns:
            Response object
        """
        return send_public_request(url=url, payload=payload)

    def scrape_with_selenium(self, url: str, payload: Optional[dict[str, Any]]) -> str:
        """Scrape a URL using Selenium WebDriver.

        Args:
            url: URL to scrape
            payload: Query parameters (unused for Selenium)

        Returns:
            HTML page source as string
        """
        try:
            chromedriver_autoinstaller.install()
        except urllib.error.URLError as e:
            log.error(f"Error with chromedriver auto-installation - {e}")
            return ""

        driver = None
        try:
            options = Options()
            options.headless = True
            options.add_argument("--headless")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument(f"user-agent={secrets.choice(user_agent_list)}")

            driver = webdriver.Chrome(options=options)
            driver.get(url)
            time.sleep(SELENIUM_WAIT_TIME)  # Allow time for JS to render
            html = driver.page_source
            return html

        except WebDriverException as e:
            log.error(f"Selenium exception: {e.msg}")
            return ""
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception as e:
                    log.warning(f"Error closing Selenium driver: {e}")

    def get_amiibo(self) -> list[dict[str, Any]]:
        """Get list of amiibo from this stockist.

        Returns:
            List of amiibo data dictionaries
        """
        raise NotImplementedError("Subclasses must implement get_amiibo()")
