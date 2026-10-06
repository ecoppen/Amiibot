import logging
import secrets
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
        adapter = HTTPAdapter(max_retries=_build_retry())
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    _session.headers.update({"User-Agent": secrets.choice(FALLBACK_USER_AGENTS)})
    return _session


class BlankResponse:
    def __init__(self):
        self.content = ""


def send_public_request(url, payload=None):
    empty_response = BlankResponse()
    if payload is None:
        payload = {}
    query_string = urlencode(payload, True)
    if query_string:
        url = url + "?" + query_string

    try:
        response = _get_session().get(url=url, timeout=REQUEST_TIMEOUT)
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
        return empty_response
    except requests.exceptions.TooManyRedirects:
        log.warning("Too many redirects")
        return empty_response
    except requests.exceptions.RetryError as e:
        log.warning(f"Retries exhausted: {e}")
        return empty_response
    except requests.exceptions.RequestException as e:
        log.warning(f"Request exception: {e}")
        return empty_response
