import logging
import time
from dataclasses import dataclass, field
from typing import Any

from constants import (
    CONSECUTIVE_UNHEALTHY_THRESHOLD,
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_FACTOR,
    STOCKIST_HEALTH_RATIO,
)
from models import deduplicate_by_url, validate_products
from result import DeliveryStatus, FailureCategory, RunResult, RunStatus

log = logging.getLogger(__name__)


@dataclass
class StockistResult:
    name: str
    success: bool
    item_count: int = 0
    duration_seconds: float = 0
    consecutive_failures: int = 0
    error: str | None = None


@dataclass
class CycleStats:
    succeeded: int
    failed: int
    notifications_sent: int
    stockist_results: list[StockistResult] = field(default_factory=list)


class Scraper:
    def __init__(self, config: Any, stockists: Any, database: Any) -> None:
        self.stockists = stockists
        self.messengers = stockists.messengers
        self.database = database
        self.config = config

    def scrape(self) -> RunResult:
        try:
            cycle = self.scrape_cycle()
            errors: list[str] = []
            for sr in cycle.stockist_results:
                if not sr.success and sr.error:
                    errors.append(f"{sr.name}: {sr.error}")
                log.info(
                    f"  {sr.name}: {'OK' if sr.success else 'FAIL'} "
                    f"items={sr.item_count} "
                    f"{sr.duration_seconds}s "
                    f"failures={sr.consecutive_failures}"
                )
            return RunResult(
                status=(RunStatus.SUCCESS if cycle.failed == 0 else RunStatus.PARTIAL),
                exit_code=0 if cycle.failed == 0 else 2,
                stockists_attempted=cycle.succeeded + cycle.failed,
                stockists_succeeded=cycle.succeeded,
                stockists_failed=cycle.failed,
                notifications_sent=cycle.notifications_sent,
                errors=errors,
            )
        except Exception as e:
            log.error(f"Scrape cycle failed: {e}", exc_info=True)
            return RunResult(
                status=RunStatus.FAILURE,
                exit_code=3,
                failure_category=FailureCategory.UNEXPECTED,
                errors=[str(e)],
            )

    def _scrape_stockist(self, stockist: Any) -> list[dict[str, Any]]:
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                return stockist.get_amiibo()
            except Exception as e:
                log.warning(
                    f"Error scraping {stockist.name} "
                    f"(attempt {attempt}/{MAX_RETRY_ATTEMPTS}): {e}"
                )
                if attempt < MAX_RETRY_ATTEMPTS:
                    wait_time = RETRY_BACKOFF_FACTOR**attempt
                    log.info(f"Retrying {stockist.name} in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
        raise RuntimeError("unreachable")

    def scrape_cycle(self) -> CycleStats:
        succeeded = 0
        failed = 0
        notifications_sent = 0
        stockist_results: list[StockistResult] = []

        for stockist in self.stockists.all_stockists:
            log.info(f"Scraping {stockist.name}")
            start_time = time.monotonic()

            try:
                scraped = self._scrape_stockist(stockist)
            except Exception as e:
                log.error(f"Error scraping {stockist.name}: {e}", exc_info=True)
                elapsed = time.monotonic() - start_time

                failure_count = self.database.record_scraping_failure(stockist.name)
                self.database.record_scrape_attempt(stockist=stockist.name)

                stockist_results.append(
                    StockistResult(
                        name=stockist.name,
                        success=False,
                        duration_seconds=round(elapsed, 2),
                        consecutive_failures=failure_count,
                        error=str(e),
                    )
                )
                failed += 1
                continue

            log.info(f"Scraped {len(scraped)} items from {stockist.name}")

            self.database.record_scrape_attempt(stockist=stockist.name)

            if len(scraped) == 0:
                failure_count = self.database.record_scraping_failure(stockist.name)

                log.warning(
                    f"No items returned from {stockist.name}. This may be a scraping failure "
                    f"or the store genuinely has no amiibo. Consecutive failures: {failure_count}. "
                    f"Skipping database update to prevent false 'delisted' notifications."
                )

                failed += 1
                continue

            validated_items, validation_errors = validate_products(scraped)
            for error in validation_errors:
                log.error(f"Invalid data from {stockist.name}: {error}")

            validated_items = deduplicate_by_url(validated_items)

            if not validated_items:
                log.warning(f"No valid items from {stockist.name} after validation")
                log.warning("Skipping database update to prevent false notifications")
                self.database.record_scraping_failure(stockist.name)
                failed += 1
                continue

            self.database.record_scraping_success(stockist.name)

            current_count = len(validated_items)
            healthy_count = self.database.get_last_healthy_count(stockist.name)
            skip_delisting = False

            if healthy_count > 0:
                ratio = current_count / healthy_count
                if ratio < STOCKIST_HEALTH_RATIO:
                    unhealthy_obs = self.database.record_unhealthy_scrape(stockist.name)

                    if unhealthy_obs < CONSECUTIVE_UNHEALTHY_THRESHOLD:
                        log.warning(
                            f"Stockist {stockist.name} may be unhealthy: "
                            f"{current_count} items vs {healthy_count} baseline "
                            f"(ratio {ratio:.2f} < {STOCKIST_HEALTH_RATIO}). "
                            f"Skipping delisting. "
                            f"({unhealthy_obs}/{CONSECUTIVE_UNHEALTHY_THRESHOLD} unhealthy observations)"
                        )
                        skip_delisting = True
                    else:
                        log.warning(
                            f"Stockist {stockist.name}: accepting new baseline of "
                            f"{current_count} items (previous: {healthy_count}) after "
                            f"{unhealthy_obs} low observations"
                        )
                        self.database.record_healthy_scrape(
                            stockist.name, current_count
                        )
                else:
                    self.database.record_healthy_scrape(stockist.name, current_count)
            else:
                self.database.record_healthy_scrape(stockist.name, current_count)

            to_notify = self.database.check_then_add_or_update_amiibo(
                validated_items, skip_delisting=skip_delisting
            )

            if len(to_notify) == 0:
                log.info(f"No changes detected for {stockist.name}")
                elapsed = time.monotonic() - start_time
                stockist_results.append(
                    StockistResult(
                        name=stockist.name,
                        success=True,
                        item_count=current_count,
                        duration_seconds=round(elapsed, 2),
                    )
                )
                succeeded += 1
                continue

            suppressed = 0
            for item in to_notify:
                if self.database.should_suppress_notification(
                    item["URL"], item["Website"], item["Stock"]
                ):
                    log.info(f"Skipping notification for {item['Title']} (cooldown)")
                    suppressed += 1
                    continue

                idempotency_key = self.database.build_idempotency_key(
                    item["URL"], item["Website"], item["Stock"]
                )

                for messenger in self.messengers.all_messengers:
                    if messenger.name not in stockist.messengers:
                        continue
                    if self.database.was_delivered_to(idempotency_key, messenger.name):
                        continue

                    result = messenger.send_embed_message(item)
                    self.database.record_delivery(
                        idempotency_key=idempotency_key,
                        website=item["Website"],
                        url=item["URL"],
                        title=item["Title"],
                        stock_status=item["Stock"],
                        messenger_name=messenger.name,
                        delivery_status=result.status.value,
                    )
                    if result.status == DeliveryStatus.SUCCESS:
                        notifications_sent += 1

                self.database.record_notification(
                    item["URL"], item["Website"], item["Stock"]
                )
            if suppressed:
                log.info(
                    f"Suppressed {suppressed} notification(s) for {stockist.name} "
                    f"(cooldown)"
                )
            elapsed = time.monotonic() - start_time
            stockist_results.append(
                StockistResult(
                    name=stockist.name,
                    success=True,
                    item_count=current_count,
                    duration_seconds=round(elapsed, 2),
                )
            )
            succeeded += 1

        return CycleStats(
            succeeded=succeeded,
            failed=failed,
            notifications_sent=notifications_sent,
            stockist_results=stockist_results,
        )
