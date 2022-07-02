import logging
import secrets
from urllib.parse import urlencode

import requests  # type: ignore

from stockist.useragents import UserAgent

log = logging.getLogger(__name__)

user_agents = UserAgent()
user_agent_list = user_agents.get_user_agents()


def dispatch_request(http_method):
    session = requests.Session()
    session.headers.update(
        {"Content-Type": "charset=utf-8", "User-Agent": secrets.choice(user_agent_list)}
    )
    return {
        "GET": session.get,
        "DELETE": session.delete,
        "PUT": session.put,
        "POST": session.post,
    }.get(http_method, "GET")


def send_public_request(url, payload=None):
    if payload is None:
        payload = {}
    query_string = urlencode(payload, True)
    if query_string:
        url = url + "?" + query_string

    log.info(f"Requesting {url}")

    response = dispatch_request("GET")(url=url)
    return response
