import logging
import time
from typing import Union

from messenger.discord import Discord
from messenger.telegram import Telegram

log = logging.getLogger(__name__)


class MessageManager:
    def __init__(self, config) -> None:
        self.all_messengers: list[Union[Discord, Telegram]] = []
        self.messenger_names: list[str] = []

        for messenger_config in config:
            if messenger_config in self.messenger_names:
                raise ValueError(
                    f"The messenger name {messenger_config} was used multiple times, it must be unique"
                )
            messenger_object = config[messenger_config]
            if messenger_object.messenger_type == "discord":
                discord = Discord(
                    name=messenger_config,
                    stockists=messenger_object.stockists,
                    webhook_url=messenger_object.webhook_url,
                    active=messenger_object.active,
                )
                self.all_messengers.append(discord)
                if messenger_object.active:
                    log.info(f"{messenger_config} setup to send messages to Discord")
                else:
                    log.info(
                        f"{messenger_config} is initialised as a Discord instance but will not send any messages"
                    )
            elif messenger_object.messenger_type == "telegram":
                self.all_messengers.append(
                    Telegram(
                        name=messenger_config,
                        stockists=messenger_object.stockists,
                        bot_token=messenger_object.bot_token,
                        chat_id=messenger_object.chat_id,
                        active=messenger_object.active,
                    )
                )
                if messenger_object.active:
                    log.info(f"{messenger_config} setup to send messages to Telegram")
                else:
                    log.info(
                        f"{messenger_config} is initialised as a Telegram instance but will not send any messages"
                    )
        self.check_for_one_messenger()

    def check_for_one_messenger(self):
        if len(self.all_messengers) < 1:
            log.error("No messengers were set to true")

    def send_message_to_all_messengers(self, message):
        for messenger in self.all_messengers:
            if messenger.active:
                messenger.send_message(message=message)
                time.sleep(0.5)

    def send_embed_message_to_all_messengers(self, embed_data):
        for messenger in self.all_messengers:
            if messenger.active:
                response = messenger.send_embed_message(embed_data=embed_data)
                log.info(response)
                time.sleep(0.5)
