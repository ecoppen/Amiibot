import logging

log = logging.getLogger(__name__)


class Messenger:
    def __init__(self, name, stockists, active):
        self.name = name
        self.stockists = stockists
        self.active = active

    messenger = None

    def send_message(self, message):
        log.info(f"Sending message: {message}")
        pass

    def send_embed_message(self, embed_data):
        log.info(f"Sending message: {embed_data}")
        pass

    def format_embed_data(self, data):
        pass
