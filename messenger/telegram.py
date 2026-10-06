import logging
import re
from typing import Any

from messenger.messenger import Messenger
from result import DeliveryResult, DeliveryStatus

log = logging.getLogger(__name__)


_MARKDOWN_SPECIALS = re.compile(r"([_*`\[])")


ELLIPSIS = "\u2026"
MAX_MESSAGE_LENGTH = 4096
# Cap for the short detail lines (price, stock, ...) so one oversized value
# cannot crowd out the title.
_MAX_VALUE_LENGTH = 256


def _escape_markdown(text: Any) -> str:
    """Escape the characters that legacy Telegram Markdown treats as markup."""
    return _MARKDOWN_SPECIALS.sub(r"\\\1", str(text))


def _escape_markdown_limited(text: Any, limit: int) -> str:
    """Escape text, truncating it first so the escaped result fits in limit.

    Truncation works on the unescaped characters (adding an ellipsis), so an
    escape sequence is never split.
    """
    raw = str(text)
    escaped = _escape_markdown(raw)
    if len(escaped) <= limit:
        return escaped
    if limit <= 0:
        return ""
    kept: list[str] = []
    used = len(ELLIPSIS)
    for char in raw:
        cost = len(_escape_markdown(char))
        if used + cost > limit:
            break
        kept.append(char)
        used += cost
    return _escape_markdown("".join(kept).rstrip()) + ELLIPSIS


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

        raw_title = embed_data.get("Title", "Stock alert")
        url = str(embed_data.get("URL", "")).replace(")", "%29").replace(" ", "%20")
        detail_lines = []
        for key in ("Price", "Stock", "Website", "Release"):
            value = embed_data.get(key)
            if value:
                escaped = _escape_markdown_limited(value, _MAX_VALUE_LENGTH)
                detail_lines.append(f"*{key}:* {escaped}")
        details = "".join(f"\n{line}" for line in detail_lines)

        # The URL cannot be truncated, so the title gets whatever room is left.
        # Truncating the title before escaping keeps escape sequences whole.
        if url:
            budget = MAX_MESSAGE_LENGTH - len(details) - len(f"[]({url})")
            if budget >= 1:
                title = _escape_markdown_limited(raw_title, budget)
                return self.send_message(f"[{title}]({url}){details}")
            log.warning("URL too long to link in a Telegram message; omitting it")
        budget = MAX_MESSAGE_LENGTH - len(details) - len("**")
        title = _escape_markdown_limited(raw_title, budget)
        return self.send_message(f"*{title}*{details}")
