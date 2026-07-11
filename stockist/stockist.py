import logging
import secrets
from enum import Enum
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from constants import (
    FALLBACK_USER_AGENTS,
    SELENIUM_WAIT_MAX,
)
from stockist.utils import send_public_request

log = logging.getLogger(__name__)

USER_AGENTS: list[str] = FALLBACK_USER_AGENTS


class Stock(Enum):
    DELISTED = "Delisted"
    IN_STOCK = "In stock"
    OUT_OF_STOCK = "Out of Stock"
    PRICE_CHANGE = "Price change"


class Stockist:
    def __init__(self, messengers: list[str]) -> None:
        self.params: dict[str, Any] = {}
        self.messengers = messengers

    base_url: str | None = None
    name: str | None = None

    def scrape(self, url: str, payload: dict[str, Any] | None) -> Any:
        return send_public_request(url=url, payload=payload)

    def scrape_with_selenium(self, url: str, payload: dict[str, Any] | None) -> str:
        driver = None
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            options.add_argument(f"user-agent={secrets.choice(USER_AGENTS)}")

            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(SELENIUM_WAIT_MAX)
            driver.set_script_timeout(SELENIUM_WAIT_MAX)

            driver.get(url)
            WebDriverWait(driver, SELENIUM_WAIT_MAX).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return driver.page_source

        except TimeoutException as e:
            log.error(f"Selenium timeout for {url[:100]}: {e}")
            return ""
        except WebDriverException as e:
            log.error(f"WebDriver exception: {e.msg}")
            return ""
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception as e:
                    log.warning(f"Error closing Selenium driver: {e}")

    def get_amiibo(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Subclasses must implement get_amiibo()")
