import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from constants import (
    CONSECUTIVE_UNHEALTHY_THRESHOLD,
    MAX_RETRY_ATTEMPTS,
    MESSAGE_SEND_DELAY,
    OUTBOX_MAX_AGE_HOURS,
    OUTBOX_MAX_ATTEMPTS,
    RETRY_BACKOFF_FACTOR,
    STOCKIST_FAILURE_ALERT_THRESHOLD,
    STOCKIST_HEALTH_RATIO,
)
from database import OUTBOX_DONE, OUTBOX_EXPIRED, ScrapingRecovery
from models import deduplicate_by_url, validate_products
from result import DeliveryStatus, FailureCategory, RunResult, RunStatus
from timeutil import utcnow

log = logging.getLogger(__name__)

_MAX_ERROR_LENGTH = 200

_FINAL_DELIVERY_STATUSES = {
    DeliveryStatus.SUCCESS.value,
    DeliveryStatus.PERMANENT_FAILURE.value,
    DeliveryStatus.INACTIVE.value,
}


@dataclass
class StockistResult:
    name: str
    success: bool
    item_count: int = 0
    duration_seconds: float = 0
    consecutive_failures: int = 0
    error: str | None = None
    recovery: ScrapingRecovery | None = None


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
                    f"failures={sr.consecutive_failures}",
                    extra={
                        "stockist": sr.name,
                        "success": sr.success,
                        "item_count": sr.item_count,
                        "duration_seconds": sr.duration_seconds,
                        "consecutive_failures": sr.consecutive_failures,
                    },
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
        except Exception as e:  # safety boundary: map any failure to a RunResult
            log.exception("Scrape cycle failed")
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
            except Exception as e:  # any stockist error is retried, then re-raised
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
            result: StockistResult | None = None
            try:
                result = self._process_stockist(stockist)
            # Deliberate safety boundary: one stockist's failure (a database
            # error, bad data, ...) must not abort the run for the others.
            except Exception as e:  # safety boundary: isolate per-stockist failures
                log.exception(f"Unexpected error processing {stockist.name}")
                result = self._record_unexpected_failure(stockist, e)
            finally:
                # Always flush, even if the scrape failed or returned nothing, so
                # events queued by earlier runs still get retried.
                notifications_sent += self._safe_flush_outbox(stockist)

            self._safe_notify_stockist_health(stockist, result)

            if result is not None:
                stockist_results.append(result)
            if result is not None and result.success:
                succeeded += 1
            else:
                failed += 1

        return CycleStats(
            succeeded=succeeded,
            failed=failed,
            notifications_sent=notifications_sent,
            stockist_results=stockist_results,
        )

    def _record_unexpected_failure(
        self, stockist: Any, error: Exception
    ) -> StockistResult:
        """Record a failure that escaped _process_stockist, never raising."""
        failure_count = 0
        try:
            failure_count = self.database.record_scraping_failure(stockist.name)
        except Exception:  # the failure handler itself must never abort the cycle
            log.exception(f"Could not record scraping failure for {stockist.name}")
        return StockistResult(
            name=stockist.name,
            success=False,
            consecutive_failures=failure_count,
            error=str(error),
        )

    def _process_stockist(self, stockist: Any) -> StockistResult | None:
        """Scrape one stockist and record changes (queuing notifications).

        Returns a StockistResult for completed or errored scrapes, or None when
        the scrape produced no usable items (counted as a failure by the caller).
        """
        log.info(f"Scraping {stockist.name}", extra={"stockist": stockist.name})
        start_time = time.monotonic()

        try:
            scraped = self._scrape_stockist(stockist)
        except Exception as e:
            log.exception(f"Error scraping {stockist.name}")
            elapsed = time.monotonic() - start_time

            failure_count = self.database.record_scraping_failure(stockist.name)
            self.database.record_scrape_attempt(stockist=stockist.name)

            return StockistResult(
                name=stockist.name,
                success=False,
                duration_seconds=round(elapsed, 2),
                consecutive_failures=failure_count,
                error=str(e),
            )

        log.info(
            f"Scraped {len(scraped)} items from {stockist.name}",
            extra={"stockist": stockist.name, "item_count": len(scraped)},
        )

        self.database.record_scrape_attempt(stockist=stockist.name)

        if len(scraped) == 0:
            failure_count = self.database.record_scraping_failure(stockist.name)

            log.warning(
                f"No items returned from {stockist.name}. This may be a scraping failure "
                f"or the store genuinely has no amiibo. Consecutive failures: {failure_count}. "
                f"Skipping database update to prevent false 'delisted' notifications."
            )
            return None

        validated_items, validation_errors = validate_products(scraped)
        for error in validation_errors:
            log.error(f"Invalid data from {stockist.name}: {error}")

        validated_items = deduplicate_by_url(validated_items)

        if not validated_items:
            log.warning(f"No valid items from {stockist.name} after validation")
            log.warning("Skipping database update to prevent false notifications")
            self.database.record_scraping_failure(stockist.name)
            return None

        recovery = self.database.record_scraping_success(stockist.name)

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
                    self.database.record_healthy_scrape(stockist.name, current_count)
            else:
                self.database.record_healthy_scrape(stockist.name, current_count)
        else:
            self.database.record_healthy_scrape(stockist.name, current_count)

        # Events are enqueued in the outbox in the same transaction as the state
        # change; they are delivered by _flush_outbox.
        queued = self.database.check_then_add_or_update_amiibo(
            validated_items, skip_delisting=skip_delisting
        )
        if len(queued) == 0:
            log.info(f"No changes detected for {stockist.name}")
        else:
            log.info(f"Queued {len(queued)} notification(s) for {stockist.name}")

        elapsed = time.monotonic() - start_time
        return StockistResult(
            name=stockist.name,
            success=True,
            item_count=current_count,
            duration_seconds=round(elapsed, 2),
            recovery=recovery if isinstance(recovery, ScrapingRecovery) else None,
        )

    def _safe_notify_stockist_health(
        self, stockist: Any, result: StockistResult | None
    ) -> None:
        """Send failure or recovery messages without ever breaking the cycle."""
        try:
            if result is not None and result.success:
                self._notify_recovery(stockist, result)
            else:
                self._notify_failure(stockist, result)
        except Exception:  # never let health messaging abort the scrape cycle
            log.exception(f"Error sending health message for {stockist.name}")

    def _send_system_message(self, stockist: Any, message: str) -> bool:
        """Send a plain text message to the stockist's messengers.

        Returns True if at least one messenger delivered it. No cooldown, outbox
        or mention is involved; failures are only logged.
        """
        delivered = False
        for messenger in self.messengers.all_messengers:
            if messenger.name not in stockist.messengers:
                continue
            try:
                result = messenger.send_message(message)
            # Safety boundary: never let a notification failure abort the
            # scrape cycle.
            except Exception as e:  # noqa: BLE001 - safety boundary
                log.error(f"{messenger.name} failed to send a health message: {e}")
                continue
            if result.status == DeliveryStatus.SUCCESS:
                delivered = True
        return delivered

    def _notify_failure(self, stockist: Any, result: StockistResult | None) -> None:
        failures, alert_sent_at = self.database.get_failure_alert_state(stockist.name)
        if failures < STOCKIST_FAILURE_ALERT_THRESHOLD or alert_sent_at is not None:
            return
        error = (result.error if result is not None else None) or "returned no items"
        error = " ".join(error.split())[:_MAX_ERROR_LENGTH]
        message = (
            f"Amiibot: {stockist.name} has failed {failures} runs in a row "
            f"(last error: {error}). Alerts for it are paused until it recovers."
        )
        if self._send_system_message(stockist, message):
            self.database.mark_failure_alert_sent(stockist.name)
        else:
            log.warning(
                f"Could not deliver the failure message for {stockist.name}; "
                f"will retry next run"
            )

    def _notify_recovery(self, stockist: Any, result: StockistResult) -> None:
        recovery = result.recovery
        if recovery is None or not recovery.alert_sent:
            return
        self._send_system_message(
            stockist,
            f"Amiibot: {stockist.name} is working again after "
            f"{recovery.previous_failures} failed runs.",
        )
        # Cleared even if the send failed, so the message is never repeated.
        self.database.clear_failure_alert(stockist.name)

    def _safe_flush_outbox(self, stockist: Any) -> int:
        try:
            return self._flush_outbox(stockist)
        except Exception:  # never let a notification failure abort the scrape cycle
            log.exception(f"Error flushing notifications for {stockist.name}")
            return 0

    def _flush_outbox(self, stockist: Any) -> int:
        """Deliver pending outbox rows for a stockist. Returns successful sends."""
        pending = self.database.get_pending_outbox(stockist.name)
        if not pending:
            return 0

        targets = [
            m for m in self.messengers.all_messengers if m.name in stockist.messengers
        ]
        max_age = timedelta(hours=OUTBOX_MAX_AGE_HOURS)
        rate_limited: set[str] = set()
        notifications_sent = 0
        sends_made = 0

        for row in pending:
            if (
                utcnow() - row.created_at > max_age
                or row.attempts >= OUTBOX_MAX_ATTEMPTS
            ):
                log.warning(
                    f"Expiring undelivered notification for {row.title} "
                    f"({row.stock_status}) after {row.attempts} attempt(s)"
                )
                self.database.complete_outbox(row.id, OUTBOX_EXPIRED)
                continue

            key = f"outbox:{row.id}"
            item = {
                "Colour": row.colour,
                "Title": row.title,
                "Image": row.image,
                "URL": row.url,
                "Price": row.price,
                "Stock": row.stock_status,
                "Website": row.website,
            }
            if row.release_date:
                item["Release"] = row.release_date
            all_final = True
            attempted = False

            for messenger in targets:
                recorded = self.database.get_delivery_status(key, messenger.name)
                if recorded in _FINAL_DELIVERY_STATUSES:
                    continue
                if messenger.name in rate_limited:
                    all_final = False
                    continue

                if sends_made:
                    time.sleep(MESSAGE_SEND_DELAY)
                sends_made += 1
                attempted = True

                result = messenger.send_embed_message(item)
                self.database.record_delivery(
                    idempotency_key=key,
                    website=row.website,
                    url=row.url,
                    title=row.title,
                    stock_status=row.stock_status,
                    messenger_name=messenger.name,
                    delivery_status=result.status.value,
                )
                if result.status == DeliveryStatus.SUCCESS:
                    notifications_sent += 1
                elif result.status == DeliveryStatus.TRANSIENT_FAILURE:
                    all_final = False
                    if result.http_status == 429:
                        log.warning(
                            f"{messenger.name} is rate limited; "
                            f"deferring remaining notifications"
                        )
                        rate_limited.add(messenger.name)

            # Rows deferred only because of rate limiting were not actually
            # tried, so they do not use up an attempt.
            if attempted:
                self.database.mark_outbox_attempt(row.id)
            if all_final:
                self.database.complete_outbox(row.id, OUTBOX_DONE)

        return notifications_sent
