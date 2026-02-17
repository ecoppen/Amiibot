import logging
import time
from typing import Any

import requests  # type: ignore

from constants import MAX_RETRY_ATTEMPTS, RETRY_BACKOFF_FACTOR

log = logging.getLogger(__name__)


class Scraper:
    def __init__(self, config: Any, stockists: Any, database: Any) -> None:
        """Initialize scraper with configuration, stockists, and database.

        Args:
            config: Configuration object
            stockists: StockistManager instance
            database: Database instance
        """
        self.stockists = stockists
        self.messengers = stockists.messengers
        self.database = database
        self.config = config

    def scrape(self) -> None:
        """Execute scraping cycle with error handling and retry logic."""
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                log.info(
                    f"Starting scrape cycle (attempt {attempt}/{MAX_RETRY_ATTEMPTS})"
                )
                self.scrape_cycle()
                log.info("Scrape cycle completed successfully")
                return
            except requests.exceptions.Timeout as e:
                log.warning(
                    f"Request timed out on attempt {attempt}/{MAX_RETRY_ATTEMPTS}: {e}"
                )
                if attempt < MAX_RETRY_ATTEMPTS:
                    wait_time = RETRY_BACKOFF_FACTOR**attempt
                    log.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    log.error("Max retry attempts reached. Scrape cycle failed.")
            except requests.exceptions.TooManyRedirects as e:
                log.error(f"Too many redirects: {e}. Not retrying.")
                break
            except requests.exceptions.RequestException as e:
                log.warning(
                    f"Request exception on attempt {attempt}/{MAX_RETRY_ATTEMPTS}: {e}"
                )
                if attempt < MAX_RETRY_ATTEMPTS:
                    wait_time = RETRY_BACKOFF_FACTOR**attempt
                    log.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    log.error("Max retry attempts reached. Scrape cycle failed.")
            except Exception as e:
                log.error(f"Unexpected error during scrape cycle: {e}", exc_info=True)
                break

    def scrape_cycle(self) -> None:
        """Execute a full scraping cycle across all configured stockists."""
        for stockist in self.stockists.all_stockists:
            log.info(f"Scraping {stockist.name}")

            try:
                scraped = stockist.get_amiibo()
            except Exception as e:
                log.error(f"Error scraping {stockist.name}: {e}", exc_info=True)

                # Record the scraping failure
                failure_count = self.database.record_scraping_failure(stockist.name)
                log.warning(
                    f"Scraping failed for {stockist.name}. "
                    f"Skipping database update to prevent false notifications. "
                    f"Consecutive failures: {failure_count}"
                )

                # Update last scraped time to track that we attempted
                self.database.update_or_insert_last_scraped(stockist=stockist.name)
                continue

            log.info(f"Scraped {len(scraped)} items from {stockist.name}")

            # Check if scraping returned no items
            if len(scraped) == 0:
                # Check how many consecutive failures we've had
                failure_count = self.database.get_consecutive_failures(stockist.name)

                # Record this as a potential failure
                failure_count = self.database.record_scraping_failure(stockist.name)

                log.warning(
                    f"No items returned from {stockist.name}. This may be a scraping failure "
                    f"or the store genuinely has no amiibo. Consecutive failures: {failure_count}. "
                    f"Skipping database update to prevent false 'delisted' notifications."
                )

                # Update last scraped time to track that we attempted
                self.database.update_or_insert_last_scraped(stockist=stockist.name)
                continue

            # Successful scrape! Record it
            self.database.record_scraping_success(stockist.name)

            # Update last scraped timestamp
            self.database.update_or_insert_last_scraped(stockist=stockist.name)

            # Validate scraped data before processing
            validated_items = []
            for item in scraped:
                try:
                    self.database._validate_amiibo_data(item)
                    validated_items.append(item)
                except ValueError as e:
                    log.error(f"Invalid data from {stockist.name}: {e}")

            if not validated_items:
                log.warning(f"No valid items from {stockist.name} after validation")
                log.warning("Skipping database update to prevent false notifications")
                continue

            # Check and update database only if we have valid items
            to_notify = self.database.check_then_add_or_update_amiibo(validated_items)

            if len(to_notify) == 0:
                log.info(f"No changes detected for {stockist.name}")
                continue

            # Send notifications
            log.info(f"Sending {len(to_notify)} notifications for {stockist.name}")
            for messenger in self.messengers.all_messengers:
                if messenger.name in stockist.messengers:
                    for item in to_notify:
                        messenger.send_embed_message(item)
