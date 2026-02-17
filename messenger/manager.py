import logging
import time
from typing import Any, Union

from constants import MESSAGE_SEND_DELAY
from messenger.discord import Discord
from messenger.telegram import Telegram

log = logging.getLogger(__name__)


class MessageManager:
    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize message manager with messenger configurations.

        Args:
            config: Dictionary of messenger configurations

        Raises:
            ValueError: If duplicate messenger names are used
        """
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

    def check_for_one_messenger(self) -> bool:
        """Validate that at least one messenger was configured.

        Returns:
            True if at least one messenger is configured
        """
        if len(self.all_messengers) < 1:
            log.error("No messengers were set to true")
            return False
        return True

    def send_message_to_all_messengers(self, message: str) -> None:
        """Send a text message to all active messengers.

        Args:
            message: Message text to send
        """
        for messenger in self.all_messengers:
            if messenger.active:
                messenger.send_message(message=message)
                time.sleep(MESSAGE_SEND_DELAY)

    def send_embed_message_to_all_messengers(self, embed_data: dict[str, Any]) -> None:
        """Send an embedded message to all active messengers.

        Args:
            embed_data: Dictionary containing message data
        """
        for messenger in self.all_messengers:
            if messenger.active:
                response = messenger.send_embed_message(embed_data=embed_data)
                log.info(response)
                time.sleep(MESSAGE_SEND_DELAY)
