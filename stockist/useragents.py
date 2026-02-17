# ruff: noqa: E501
import logging
import secrets

import requests  # type: ignore
from bs4 import BeautifulSoup

from constants import REQUEST_TIMEOUT

log = logging.getLogger(__name__)


class UserAgent:
    """Manages user agent strings for web scraping."""

    def __init__(self) -> None:
        """Initialize with base user agents."""
        self.base_agents: list[str] = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.10 Safari/605.1.1",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.3",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.3",
        ]
        self.base_agents = [
            item.replace("\n", "").replace("\r", "").replace("\t", "")
            for item in self.base_agents
        ]

    def get_user_agents(self) -> list[str]:
        """Get list of user agents, updating from online source if possible.

        Returns:
            List of user agent strings (always returns at least base agents)
        """
        agent = (
            secrets.choice(self.base_agents)
            .replace("\n", "")
            .replace("\r", "")
            .replace("\t", "")
        )
        log.info(f"Using {agent} to scrape for new agents >.>")
        headers = {"User-Agent": agent}
        try:
            page = requests.get(
                "https://www.useragents.me", headers=headers, timeout=REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            log.warning("User-agent scraper timeout, using base agents")
            return self.base_agents
        except requests.exceptions.ConnectionError:
            log.warning("User-agent connection error, using base agents")
            return self.base_agents
        except requests.exceptions.HTTPError:
            log.warning("User-agent HTTP error, using base agents")
            return self.base_agents
        except Exception as e:
            log.warning(
                f"Unexpected error fetching user agents: {e}, using base agents"
            )
            return self.base_agents

        try:
            soup = BeautifulSoup(page.content, "html.parser")
            agents = soup.find_all("textarea", class_="form-control")
            if len(agents) > 0:
                new_agents = [
                    f"{link.string}".replace("\n", "")
                    .replace("\r", "")
                    .replace("\t", "")
                    for link in agents[:25]
                ]
                if new_agents:  # Only update if we got valid agents
                    self.base_agents = new_agents
                    log.info(
                        f"Scraped {len(new_agents)} user-agents to use instead of default list"
                    )
        except Exception as e:
            log.warning(f"Error parsing user agents: {e}, using base agents")

        return self.base_agents
