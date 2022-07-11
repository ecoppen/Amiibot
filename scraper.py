import logging
import subprocess  # nosec
import time

import requests  # type: ignore

log = logging.getLogger(__name__)


class Scraper:
    def __init__(self, config, stockists, database) -> None:
        self.interval = config.scrape_interval
        self.heartbeat = config.heartbeat
        self.notify_first_run = config.notify_first_run
        self.check_version_daily = config.check_version_daily

        self.stockists = stockists
        self.messengers = stockists.messengers
        self.database = database

    def get_current_version(self):
        args = ["git", "describe", "--always"]
        return subprocess.check_output(args, shell=False).strip().decode()  # nosec

    def get_latest_version(self):
        response = requests.get(
            "https://api.github.com/repos/ecoppen/Amiibot/commits"
        ).json()
        if len(response) > 0 and isinstance(response, list):
            if "sha" in response[0]:
                return response[0]["sha"][:7]
        log.warning("Could not get latest version reference from github API")
        return False

    def compare_current_to_latest(self):
        current = self.get_current_version()
        latest = self.get_latest_version()
        if current == latest:
            log.info("Amiibot is up-to-date")
        else:
            if latest:
                log.warning("There's a new version of Amiibot!")
                self.messengers.send_message_to_all_messengers(
                    message="There's a new version of Amiibot!"
                )
        self.database.update_or_insert_last_scraped(stockist="github.com")

    def _auto_scrape(self):
        while True:
            log.info("Auto scrape routines starting")
            self.scrape()
            log.info(
                f"Auto scrape routines terminated. Sleeping {self.interval} seconds..."
            )
            time.sleep(self.interval)

    def scrape(self):
        try:
            self.scrape_cycle()
        except requests.exceptions.Timeout:
            log.warning("Request timed out")
        except requests.exceptions.TooManyRedirects:
            log.warning("Too many redirects")
        except requests.exceptions.RequestException as e:
            log.warning(f"Request exception: {e}")

    def scrape_cycle(self):
        if (
            self.check_version_daily
            and self.database.get_days_since_last_github_check() > 0
        ):
            self.compare_current_to_latest()
