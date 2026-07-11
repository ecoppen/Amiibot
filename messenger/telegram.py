import logging

from messenger.messenger import Messenger
from result import DeliveryStatus

log = logging.getLogger(__name__)


class Telegram(Messenger):
    def __init__(
        self,
        name: str,
        stockists: list[str],
        active: bool,
        bot_token: str,
        chat_id: str,
    ) -> None:
        super().__init__(name=name, stockists=stockists, active=active)
        self.bot_token = bot_token
        self.data: dict[str, str] = {
            "chat_id": chat_id,
            "parse_mode": "Markdown",
        }

    messenger = "telegram"

    def send_message(self, message: str):
        if self.active:
            log.info(f"Sending telegram message to {self.name}")
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            self.data["text"] = message
            return self.send_get(url=url, params=self.data)
        return self._build_delivery_result(DeliveryStatus.INACTIVE)
