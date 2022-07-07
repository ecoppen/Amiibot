import logging

import requests  # type: ignore

from messenger.messenger import Messenger

log = logging.getLogger(__name__)


class Telegram(Messenger):
    def __init__(self, name, stockists, bot_token, chat_id):
        super().__init__(name=name, stockists=stockists)
        self.bot_token = bot_token
        self.chat_id = chat_id

    messenger = "telegram"

    def send_message(self, message):
        log.info(f"Sending telegram message: {message}")
        send_text = f"https://api.telegram.org/bot{self.bot_token}/sendMessage?chat_id={self.chat_id}&parse_mode=Markdown&text={message}"

        response = requests.get(send_text)

        return response.json()
