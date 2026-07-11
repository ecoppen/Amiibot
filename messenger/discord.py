import logging
from datetime import datetime
from typing import Any

from messenger.messenger import Messenger
from result import DeliveryResult, DeliveryStatus

log = logging.getLogger(__name__)


class Discord(Messenger):
    def __init__(
        self, name: str, stockists: list[str], active: bool, webhook_url: str
    ) -> None:
        super().__init__(name=name, stockists=stockists, active=active)
        self.webhook_url = webhook_url
        self.data: dict[str, Any] = {
            "username": "Amiibot",
            "avatar_url": "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png",
        }

    messenger = "discord"

    def send_message(self, message: str) -> DeliveryResult:
        if self.active:
            log.info(f"Sending discord message via {self.name}: {message}")
            self.data["content"] = message
            return self.send_post(url=self.webhook_url, json=self.data)
        return self._build_delivery_result(DeliveryStatus.INACTIVE)

    def send_embed_message(self, embed_data: dict[str, Any]) -> DeliveryResult:
        if not self.active:
            return self._build_delivery_result(DeliveryStatus.INACTIVE)

        log.info(f"Sending embedded discord message via {self.name}")

        options, payload = self.format_embed_data(embed_data)

        self.data["content"] = "Stock alert"

        embed: dict[str, Any] = {"fields": []}
        for k, v in options.items():
            embed[k] = v
        for k, v in payload.items():
            embed["fields"].append({"name": k, "value": f"{v}", "inline": True})
        embed["footer"] = {
            "text": f"Amiibot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "icon_url": "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png",
        }
        self.data["embeds"] = [embed]

        result = self.send_post(url=self.webhook_url, json=self.data)
        return result

    def format_embed_data(
        self, embed_data: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        options_keys = {
            "Title": "title",
            "Colour": "color",
            "URL": "url",
            "Image": "thumbnail",
        }
        payload_keys = ["Price", "Stock", "Website"]
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
