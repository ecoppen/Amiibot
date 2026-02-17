import logging
from typing import Optional, Union

import requests  # type: ignore

from messenger.messenger import BlankResponse, Messenger

log = logging.getLogger(__name__)


class Telegram(Messenger):
    """Telegram bot messenger for sending stock alerts."""

    def __init__(
        self,
        name: str,
        stockists: list[str],
        active: bool,
        bot_token: str,
        chat_id: str,
    ) -> None:
        """Initialize Telegram messenger.

        Args:
            name: Name identifier for the messenger
            stockists: List of stockist URLs this messenger tracks
            active: Whether this messenger is active
            bot_token: Telegram bot API token
            chat_id: Telegram chat ID to send messages to
        """
        super().__init__(name=name, stockists=stockists, active=active)
        self.bot_token = bot_token
        self.data = {
            "chat_id": chat_id,
            "parse_mode": "Markdown",
        }

    messenger = "telegram"

    def send_message(
        self, message: str
    ) -> Optional[Union[requests.Response, BlankResponse]]:
        """Send a text message to Telegram.

        Args:
            message: Message text to send

        Returns:
            Response object or None if inactive
        """
        if self.active:
            log.info(f"Sending telegram message to {self.name}: {message}")
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            self.data["text"] = message

            return self.send_get(url=url, params=self.data)
        log.info(f"{self.name} (telegram messenger) is inactive")
        return None
