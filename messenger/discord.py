import logging
from datetime import datetime
from typing import Any, Optional, Union

import requests  # type: ignore

from messenger.messenger import BlankResponse, Messenger

log = logging.getLogger(__name__)


class Discord(Messenger):
    """Discord webhook messenger for sending stock alerts."""

    def __init__(
        self, name: str, stockists: list[str], active: bool, webhook_url: str
    ) -> None:
        """Initialize Discord messenger.

        Args:
            name: Name identifier for the messenger
            stockists: List of stockist URLs this messenger tracks
            active: Whether this messenger is active
            webhook_url: Discord webhook URL
        """
        super().__init__(name=name, stockists=stockists, active=active)
        self.webhook_url = webhook_url

    messenger = "discord"
    data: dict[str, Any] = {
        "username": "Amiibot",
        "avatar_url": "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png",
    }

    def send_message(
        self, message: str
    ) -> Optional[Union[requests.Response, BlankResponse]]:
        """Send a text message to Discord.

        Args:
            message: Message text to send

        Returns:
            Response object or None if inactive
        """
        if self.active:
            log.info(f"Sending discord message via {self.name}: {message}")
            self.data["content"] = message
            return self.send_post(url=self.webhook_url, json=self.data)
        log.info(f"{self.name} (discord messenger) is inactive")
        return None

    def send_embed_message(
        self, embed_data: dict[str, Any]
    ) -> Optional[Union[requests.Response, BlankResponse]]:
        """Send an embedded message to Discord.

        Args:
            embed_data: Dictionary containing message data (Title, Colour, URL, Image, Price, Stock, Website)

        Returns:
            Response object or None if inactive
        """
        if self.active:
            log.info(f"Sending embedded discord message via {self.name}: {embed_data}")

            options, payload = self.format_embed_data(embed_data)

            self.data["content"] = "Stock alert"

            self.data["embeds"] = [
                {
                    "fields": [],
                }
            ]

            for k, v in options.items():
                self.data["embeds"][0][k] = v

            for k, v in payload.items():
                self.data["embeds"][0]["fields"].append(
                    {"name": k, "value": f"{v}", "inline": True}
                )
            self.data["embeds"][0]["footer"] = {
                "text": f"Amiibot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "icon_url": "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png",
            }
            log.info(f"Final embed data: {self.data}")
            response = self.send_post(url=self.webhook_url, json=self.data)

            if response and hasattr(response, "status_code"):
                log.info(f"Discord API response status: {response.status_code}")

            return response

        log.info(f"{self.name} (discord messenger) is inactive")
        return None

    def format_embed_data(
        self, embed_data: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Format embed data for Discord API.

        Args:
            embed_data: Raw embed data dictionary

        Returns:
            Tuple of (options, payload) dictionaries
        """
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
