import logging
import re
from typing import Any

from messenger.messenger import Messenger
from result import DeliveryResult, DeliveryStatus

log = logging.getLogger(__name__)


_MARKDOWN_SPECIALS = re.compile(r"([_*`\[])")


def _escape_markdown(text: Any) -> str:
    """Escape the characters that legacy Telegram Markdown treats as markup."""
    return _MARKDOWN_SPECIALS.sub(r"\\\1", str(text))


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

    def send_embed_message(self, embed_data: dict[str, Any]) -> DeliveryResult:
        if not self.active:
            return self._build_delivery_result(DeliveryStatus.INACTIVE)

        title = _escape_markdown(embed_data.get("Title", "Stock alert"))
        url = str(embed_data.get("URL", "")).replace(")", "%29").replace(" ", "%20")
        lines = [f"[{title}]({url})" if url else f"*{title}*"]
        for key in ("Price", "Stock", "Website", "Release"):
            value = embed_data.get(key)
            if value:
                lines.append(f"*{key}:* {_escape_markdown(value)}")

        return self.send_message("\n".join(lines))
