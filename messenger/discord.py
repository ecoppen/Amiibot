import logging
from datetime import datetime

import requests  # type: ignore

from messenger.messenger import Messenger

log = logging.getLogger(__name__)


class Discord(Messenger):
    def __init__(self, name, webhook_url):
        super().__init__(name)
        self.webhook_url = webhook_url

    messenger = "discord"
    data = {
        "username": "Amiibot",
        "avatar_url": "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png",
    }

    def send_message(self, message):
        log.info(f"Sending discord message: {message}")
        self.data["content"] = message
        response = requests.post(self.webhook_url, json=self.data)
        return response

    def send_embed_message(self, embed_data):
        log.info(f"Sending embedded discord message: {embed_data}")

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
                {"name": k, "value": v, "inline": True}
            )
        self.data["embeds"][0]["footer"] = {
            "text": f"Amiibot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "icon_url": "https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png",
        }
        response = requests.post(self.webhook_url, json=self.data)

        return response

    def format_embed_data(self, embed_data):
        options_keys = {
            "Title": "title",
            "Colour": "color",
            "URL": "url",
            "Image": "thumbnail",
        }
        payload_keys = ["Price", "Stock", "Website"]
        options = {}
        payload = {}
        for k, v in embed_data.items():
            if k in options_keys:
                if k == "Image":
                    options[options_keys[k]] = {"url": v}
                else:
                    options[options_keys[k]] = v

            elif k in payload_keys:
                payload[k] = v

        return options, payload