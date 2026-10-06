import logging
from typing import Any

from messenger.messenger import Messenger
from result import DeliveryResult, DeliveryStatus
from stockist.stockist import URGENT_STATUSES
from timeutil import utcnow

log = logging.getLogger(__name__)


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
            "content": content,
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
        for k, v in payload.items():
            embed["fields"].append({"name": k, "value": f"{v}", "inline": True})
        # Discord renders the timestamp in each viewer's local time.
        embed["timestamp"] = utcnow().isoformat()
        embed["footer"] = {"text": "Amiibot", "icon_url": AVATAR_URL}

        data = self._new_payload("Stock alert")
        if self.mention and embed_data.get("Stock") in URGENT_STATUSES:
            data["content"] = f"{self.mention} Stock alert"
            data["allowed_mentions"] = self._allowed_mentions()
        data["embeds"] = [embed]

        return self.send_post(url=self.webhook_url, json=data)

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
