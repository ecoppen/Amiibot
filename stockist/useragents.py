# ruff: noqa: E501
import logging
import secrets

import requests  # type: ignore
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


class UserAgent:
    def __init__(self):
        self.base_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.10 Safari/605.1.1",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.3",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
        ]
        self.base_agents = [
            item.replace("\n", "").replace("\r", "").replace("\t", "")
            for item in self.base_agents
        ]

    def get_user_agents(self):
        agent = (
            secrets.choice(self.base_agents)
            .replace("\n", "")
            .replace("\r", "")
            .replace("\t", "")
        )
        log.info(f"Using {agent} to scrape for new agents >.>")
        headers = {"User-Agent": agent}
        try:
            page = requests.get("https://www.useragents.me", headers=headers, timeout=5)
        except TimeoutError:
            log.warning("User-agent scraper timeout")
            return self.base_agents
        except requests.exceptions.ConnectionError:
            log.warning("User-agent connection error")
            return self.base_agents
        except requests.exceptions.HTTPError:
            log.warning("User-agent HTTP error")
            return self.base_agents

        soup = BeautifulSoup(page.content, "html.parser")
        agents = soup.find_all("textarea", class_="form-control")
        if len(agents) > 0:
            self.base_agents = [
                f"{link.string}".replace("\n", "").replace("\r", "").replace("\t", "")
                for link in agents[:25]
            ]
            log.info("Scraped 25 user-agents to use instead of default list")
        return self.base_agents
