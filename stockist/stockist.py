import logging
import secrets
from enum import Enum
from typing import Any

import urllib3
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from constants import (
    FALLBACK_USER_AGENTS,
    REQUEST_TIMEOUT,
    SELENIUM_WAIT_MAX,
)
from stockist.utils import build_url, send_public_post, send_public_request

log = logging.getLogger(__name__)

USER_AGENTS: list[str] = FALLBACK_USER_AGENTS


class Stock(Enum):
    DELISTED = "Delisted"
    IN_STOCK = "In stock"
    OUT_OF_STOCK = "Out of Stock"
    PRICE_CHANGE = "Price change"
    PRE_ORDER = "Pre-order"


# Stock statuses that always notify, bypassing the repeat-alert cooldown, and
# that ping the configured Discord mention.
URGENT_STATUSES: frozenset[str] = frozenset(
    {Stock.IN_STOCK.value, Stock.PRE_ORDER.value}
)


class Stockist:
    def __init__(self, messengers: list[str]) -> None:
        self.params: dict[str, Any] | None = {}
        self.messengers = messengers

    base_url: str | None = None
    name: str | None = None
    # Seconds to wait for a response; a slow shop can override this.
    request_timeout: float = REQUEST_TIMEOUT

    def scrape(self, url: str, payload: dict[str, Any] | None) -> Any:
        return send_public_request(
            url=url, payload=payload, timeout=self.request_timeout
        )

    def post(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        data: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return send_public_post(
            url=url,
            params=params,
            data=data,
            headers=headers,
            timeout=self.request_timeout,
        )

    def scrape_with_selenium(
        self,
        url: str,
        payload: dict[str, Any] | None,
        wait_for: str | None = None,
    ) -> str:
        """Load a page in headless Chrome and return its HTML.

        `wait_for` is an optional CSS selector for pages that fill in their
        content with JavaScript after loading. If it never appears, the page
        is returned as it stands.
        """
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

            driver.get(build_url(url, payload))
            WebDriverWait(driver, SELENIUM_WAIT_MAX).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            if wait_for:
                try:
                    WebDriverWait(driver, SELENIUM_WAIT_MAX).until(
                        lambda d: d.find_elements(By.CSS_SELECTOR, wait_for)
                    )
                except TimeoutException:
                    log.warning(f"Timed out waiting for {wait_for!r} on {url[:100]}")
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
                except (WebDriverException, OSError, urllib3.exceptions.HTTPError) as e:
                    log.warning(f"Error closing Selenium driver: {e}")

    def get_amiibo(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Subclasses must implement get_amiibo()")
