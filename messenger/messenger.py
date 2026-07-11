import logging
from typing import Any

import requests  # type: ignore

from constants import REQUEST_TIMEOUT
from result import DeliveryResult, DeliveryStatus

log = logging.getLogger(__name__)


class Messenger:
    def __init__(self, name: str, stockists: list[str], active: bool) -> None:
        self.name = name
        self.stockists = stockists
        self.active = active

    messenger: str | None = None

    def _classify_response(self, response: requests.Response) -> DeliveryStatus:
        code = response.status_code
        if 200 <= code < 300:
            return DeliveryStatus.SUCCESS
        if code == 429 or code >= 500:
            return DeliveryStatus.TRANSIENT_FAILURE
        return DeliveryStatus.PERMANENT_FAILURE

    def _build_delivery_result(
        self,
        status: DeliveryStatus,
        http_status: int | None = None,
        diagnostic: str | None = None,
    ) -> DeliveryResult:
        return DeliveryResult(
            status=status,
            messenger_name=self.name,
            http_status=http_status,
            diagnostic=diagnostic,
        )

    def send_post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        timeout: int = REQUEST_TIMEOUT,
    ) -> DeliveryResult:
        try:
            response = requests.post(url, json=json, timeout=timeout)
            status = self._classify_response(response)
            return self._build_delivery_result(status, response.status_code)
        except requests.exceptions.Timeout:
            return self._build_delivery_result(
                DeliveryStatus.TRANSIENT_FAILURE, diagnostic="timeout"
            )
        except requests.exceptions.ConnectionError as e:
            return self._build_delivery_result(
                DeliveryStatus.TRANSIENT_FAILURE, diagnostic=f"connection: {e}"
            )
        except requests.exceptions.TooManyRedirects:
            return self._build_delivery_result(
                DeliveryStatus.PERMANENT_FAILURE, diagnostic="too many redirects"
            )
        except requests.exceptions.RequestException as e:
            return self._build_delivery_result(
                DeliveryStatus.TRANSIENT_FAILURE, diagnostic=str(e)
            )

    def send_get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        timeout: int = REQUEST_TIMEOUT,
    ) -> DeliveryResult:
        try:
            response = requests.get(url, params=params, timeout=timeout)
            status = self._classify_response(response)
            return self._build_delivery_result(status, response.status_code)
        except requests.exceptions.Timeout:
            return self._build_delivery_result(
                DeliveryStatus.TRANSIENT_FAILURE, diagnostic="timeout"
            )
        except requests.exceptions.ConnectionError as e:
            return self._build_delivery_result(
                DeliveryStatus.TRANSIENT_FAILURE, diagnostic=f"connection: {e}"
            )
        except requests.exceptions.TooManyRedirects:
            return self._build_delivery_result(
                DeliveryStatus.PERMANENT_FAILURE, diagnostic="too many redirects"
            )
        except requests.exceptions.RequestException as e:
            return self._build_delivery_result(
                DeliveryStatus.TRANSIENT_FAILURE, diagnostic=str(e)
            )

    def send_message(self, message: str) -> DeliveryResult:
        return self._build_delivery_result(DeliveryStatus.INACTIVE)

    def send_embed_message(self, embed_data: dict[str, Any]) -> DeliveryResult:
        return self._build_delivery_result(DeliveryStatus.INACTIVE)
