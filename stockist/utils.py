import logging
import secrets
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import requests  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from urllib3.util import Retry

from constants import FALLBACK_USER_AGENTS, REQUEST_TIMEOUT

log = logging.getLogger(__name__)

_session: requests.Session | None = None


RETRY_TOTAL = 2
RETRY_BACKOFF_FACTOR = 1
RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)

# Browser-like defaults. Some shops (bestbuy.ca, for one) stall requests that
# do not look like they come from a browser.
DEFAULT_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/json;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


def _build_retry() -> Retry:
    return Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        allowed_methods={"GET"},
        # A shop can send an arbitrarily long Retry-After; never stall the run on it.
        respect_retry_after_header=False,
        raise_on_status=False,
    )


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(DEFAULT_HEADERS)
        adapter = HTTPAdapter(max_retries=_build_retry())
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    _session.headers.update({"User-Agent": secrets.choice(FALLBACK_USER_AGENTS)})
    return _session


class BlankResponse:
    """Stand-in returned when a request fails; its body is empty bytes.

    `status_code` is the HTTP status when the shop answered with an error, and
    None when there was no answer at all (a timeout, say).
    """

    def __init__(self, status_code: int | None = None):
        self.content = b""
        self.status_code = status_code


def build_url(url: str, payload: dict[str, Any] | None = None) -> str:
    """Append a urlencoded payload to a URL as a query string."""
    query_string = urlencode(payload or {}, True)
    if not query_string:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query_string}"


def _guarded(send: Callable[[], Any]) -> Any:
    """Run a request, returning a BlankResponse instead of raising on failure."""
    empty_response = BlankResponse()
    try:
        response = send()
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout:
        log.info("Request timed out")
        return empty_response
    except requests.exceptions.ConnectionError as e:
        log.warning(f"Connection error: {e}")
        return empty_response
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP error: {e}")
        failed = getattr(e, "response", None)
        return BlankResponse(getattr(failed, "status_code", None))
    except requests.exceptions.TooManyRedirects:
        log.warning("Too many redirects")
        return empty_response
    except requests.exceptions.RetryError as e:
        log.warning(f"Retries exhausted: {e}")
        return empty_response
    except requests.exceptions.RequestException as e:
        log.warning(f"Request exception: {e}")
        return empty_response


def send_public_request(url, payload=None, timeout=REQUEST_TIMEOUT):
    url = build_url(url, payload)
    return _guarded(lambda: _get_session().get(url=url, timeout=timeout))


def send_public_post(
    url, params=None, data=None, headers=None, timeout=REQUEST_TIMEOUT
):
    """POST through the shared session (so it has the same default headers).

    Unlike GET requests, POSTs are not retried.
    """
    return _guarded(
        lambda: _get_session().post(
            url=url, params=params, data=data, headers=headers, timeout=timeout
        )
    )
