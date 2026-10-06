import logging
from typing import Any

from messenger.messenger import Messenger
from result import DeliveryResult, DeliveryStatus
from stockist.stockist import URGENT_STATUSES
from timeutil import utcnow

log = logging.getLogger(__name__)


ELLIPSIS = "\u2026"

# Discord's documented limits; requests over them are rejected with HTTP 400,
# which would be classified as a permanent failure and lose the alert.
MAX_CONTENT_LENGTH = 2000
MAX_TITLE_LENGTH = 256
MAX_FIELD_NAME_LENGTH = 256
MAX_FIELD_VALUE_LENGTH = 1024
MAX_FOOTER_LENGTH = 2048
MAX_EMBED_TOTAL_LENGTH = 6000


def _truncate(text: str, limit: int) -> str:
    """Shorten text to at most limit characters, ending with an ellipsis."""
    if len(text) <= limit:
        return text
    if limit <= len(ELLIPSIS):
        return ELLIPSIS[:limit]
    return text[: limit - len(ELLIPSIS)].rstrip() + ELLIPSIS


AVATAR_URL = "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png"


class Discord(Messenger):
    def __init__(
        self,
        name: str,
        stockists: list[str],
        active: bool,
        webhook_url: str,
        mention: str | None = None,
    ) -> None:
        super().__init__(name=name, stockists=stockists, active=active)
        self.webhook_url = webhook_url
        self.mention = mention

    messenger = "discord"

    @staticmethod
    def _new_payload(content: str) -> dict[str, Any]:
        """Build a fresh webhook payload so nothing leaks between sends."""
        return {
            "username": "Amiibot",
            "avatar_url": AVATAR_URL,
            "content": _truncate(content, MAX_CONTENT_LENGTH),
            "allowed_mentions": {"parse": []},
        }

    def _allowed_mentions(self) -> dict[str, Any]:
        """Allow exactly the configured mention to ping, and nothing else."""
        mention = self.mention or ""
        if mention.startswith("<@&"):
            return {"roles": [mention[3:-1]]}
        if mention.startswith("<@"):
            return {"users": [mention[2:-1]]}
        return {"parse": ["everyone"]}

    def send_message(self, message: str) -> DeliveryResult:
        if self.active:
            log.info(f"Sending discord message via {self.name}: {message}")
            return self.send_post(url=self.webhook_url, json=self._new_payload(message))
        return self._build_delivery_result(DeliveryStatus.INACTIVE)

    def send_embed_message(self, embed_data: dict[str, Any]) -> DeliveryResult:
        if not self.active:
            return self._build_delivery_result(DeliveryStatus.INACTIVE)

        log.info(f"Sending embedded discord message via {self.name}")

        options, payload = self.format_embed_data(embed_data)

        embed: dict[str, Any] = {"fields": []}
        for k, v in options.items():
            embed[k] = v
        if "title" in embed:
            embed["title"] = _truncate(str(embed["title"]), MAX_TITLE_LENGTH)
        for k, v in payload.items():
            embed["fields"].append(
                {
                    "name": _truncate(str(k), MAX_FIELD_NAME_LENGTH),
                    "value": _truncate(f"{v}", MAX_FIELD_VALUE_LENGTH),
                    "inline": True,
                }
            )
        # Discord renders the timestamp in each viewer's local time.
        embed["timestamp"] = utcnow().isoformat()
        embed["footer"] = {
            "text": _truncate("Amiibot", MAX_FOOTER_LENGTH),
            "icon_url": AVATAR_URL,
        }
        self._fit_embed_total(embed)

        data = self._new_payload("Stock alert")
        if self.mention and embed_data.get("Stock") in URGENT_STATUSES:
            data["content"] = f"{self.mention} Stock alert"
            data["allowed_mentions"] = self._allowed_mentions()
        data["embeds"] = [embed]

        return self.send_post(url=self.webhook_url, json=data)

    @staticmethod
    def _fit_embed_total(embed: dict[str, Any]) -> None:
        """Shrink the longest free-text strings until the embed fits the total limit.

        Discord counts title, description, field names and values, and footer
        text towards one 6000 character limit. URLs and thumbnails do not count
        and are never touched.
        """

        def total() -> int:
            size = len(embed.get("title", "")) + len(embed.get("description", ""))
            size += len(embed.get("footer", {}).get("text", ""))
            for field_ in embed["fields"]:
                size += len(field_["name"]) + len(field_["value"])
            return size

        excess = total() - MAX_EMBED_TOTAL_LENGTH
        while excess > 0:
            candidates: list[tuple[dict[str, Any], str]] = [
                (field_, "value") for field_ in embed["fields"]
            ]
            if "title" in embed:
                candidates.append((embed, "title"))
            holder, key = max(candidates, key=lambda c: len(c[0][c[1]]))
            current = holder[key]
            new_length = max(len(current) - excess, len(ELLIPSIS))
            if new_length >= len(current):
                break  # nothing left to shrink
            holder[key] = _truncate(current, new_length)
            excess = total() - MAX_EMBED_TOTAL_LENGTH

    def format_embed_data(
        self, embed_data: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        options_keys = {
            "Title": "title",
            "Colour": "color",
            "URL": "url",
            "Image": "thumbnail",
        }
        payload_keys = ["Price", "Stock", "Website", "Release"]
        options: dict[str, Any] = {}
        payload: dict[str, Any] = {}
        for k, v in embed_data.items():
            if k in options_keys:
                if k == "Image":
                    options[options_keys[k]] = {"url": v.replace(" ", "%20")}
                else:
                    options[options_keys[k]] = v
            elif k in payload_keys:
                payload[k] = v

        return options, payload
