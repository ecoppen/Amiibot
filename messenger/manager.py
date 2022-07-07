import logging
import time

from messenger.discord import Discord
from messenger.telegram import Telegram

log = logging.getLogger(__name__)


class MessageManager:
    def __init__(self, config) -> None:
        self.all_messengers = []

        for messenger_config in config:
            messenger_object = config[messenger_config]
            if messenger_object.active:
                if messenger_object.messenger_type == "discord":
                    discord = Discord(
                        name=messenger_config,
                        stockists=messenger_object.stockists,
                        webhook_url=messenger_object.webhook_url,
                    )
                    self.all_messengers.append(discord)
                    log.info(f"{messenger_config} setup to send messages to Discord")
                    discord.send_message(f"{messenger_config} initialised")
                elif messenger_object.messenger_type == "telegram":
                    self.all_messengers.append(
                        Telegram(
                            name=messenger_config,
                            stockists=messenger_object.stockists,
                            bot_token=messenger_object.bot_token,
                            chat_id=messenger_object.chat_id,
                        )
                    )
                    log.info(f"{messenger_config} setup to send messages to Telegram")
        self.check_for_one_messenger()

    def check_for_one_messenger(self):
        if len(self.all_messengers) < 1:
            log.error("No messengers were set to true")

    def send_message_to_all_messengers(self, message):
        for messenger in self.all_messengers:
            messenger.send_message(message=message)
            time.sleep(0.5)

    def send_embed_message_to_all_messengers(self, embed_data):
        for messenger in self.all_messengers:
            messenger.send_embed_message(embed_data=embed_data)
            time.sleep(0.5)
