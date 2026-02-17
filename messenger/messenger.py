import logging
from typing import Any, Optional, Union

import requests  # type: ignore

from constants import REQUEST_TIMEOUT

log = logging.getLogger(__name__)


class BlankResponse:
    """Mock response object for failed requests."""

    def __init__(self) -> None:
        self.content = ""


class Messenger:
    """Base messenger class for sending notifications."""

    def __init__(self, name: str, stockists: list[str], active: bool) -> None:
        """Initialize messenger.

        Args:
            name: Name identifier for the messenger
            stockists: List of stockist URLs this messenger tracks
            active: Whether this messenger is active
        """
        self.name = name
        self.stockists = stockists
        self.active = active
        self.empty_response = BlankResponse()

    messenger: Optional[str] = None

    def send_post(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        timeout: int = REQUEST_TIMEOUT,
    ) -> Union[requests.Response, BlankResponse]:
        """Send a POST request with error handling.

        Args:
            url: URL to POST to
            json: JSON data to send
            timeout: Request timeout in seconds

        Returns:
            Response object or BlankResponse on error
        """
        try:
            response = requests.post(url, json=json, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            log.info("Request timed out")
            return self.empty_response
        except requests.exceptions.TooManyRedirects:
            log.warning("Too many redirects")
            return self.empty_response
        except requests.exceptions.RequestException as e:
            log.warning(f"Request exception: {e}")
            return self.empty_response

    def send_get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        timeout: int = REQUEST_TIMEOUT,
    ) -> Union[requests.Response, BlankResponse]:
        """Send a GET request with error handling.

        Args:
            url: URL to GET from
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            Response object or BlankResponse on error
        """
        try:
            response = requests.get(url, params=params, timeout=timeout)
            return response
        except requests.exceptions.Timeout:
            log.info("Request timed out")
            return self.empty_response
        except requests.exceptions.TooManyRedirects:
            log.warning("Too many redirects")
            return self.empty_response
        except requests.exceptions.RequestException as e:
            log.warning(f"Request exception: {e}")
            return self.empty_response

    def send_message(self, message):
        log.info(f"Sending message: {message}")
        pass

    def send_embed_message(self, embed_data):
        log.info(f"Sending message: {embed_data}")
        pass

    def format_embed_data(self, data):
        pass
