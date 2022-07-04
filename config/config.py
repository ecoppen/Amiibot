import json
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import (
    BaseModel,
    Extra,
    Field,
    HttpUrl,
    IPvAnyAddress,
    ValidationError,
    validator,
)
from typing_extensions import Annotated


class Databases(Enum):
    POSTGRES = "postgres"
    SQLITE = "sqlite"


class MESSENGER(Enum):
    DISCORD = "discord"
    TELEGRAM = "telegram"


class Stockist(Enum):
    SHOPTO = "shopto.net"
    GAMEUK = "game.co.uk"
    NINTENDOUK = "nintendo.co.uk"
    GAMESTOP = "gamestop.com"
    BESTBUY = "bestbuy.com"
    BESTBUYCA = "bestbuy.ca"
    PLAYASIA = "play-asia.com"


class Database(BaseModel, use_enum_values=True, extra=Extra.forbid):
    engine: str = Databases.SQLITE  # type: ignore
    username: Optional[str]
    password: Optional[str]
    host: Optional[IPvAnyAddress] = IPvAnyAddress.validate("127.0.0.1")  # type: ignore
    port: Optional[int] = Field(5432, ge=1, le=65535)
    name: str = "amiiboalert"


class Discord(BaseModel, use_enum_values=True, extra=Extra.forbid):
    active: bool = False
    messenger_type: Literal[MESSENGER.DISCORD.value]  # type: ignore
    webhook_url: HttpUrl


class Telegram(BaseModel, use_enum_values=True, extra=Extra.forbid):
    active: bool = False
    messenger_type: Literal[MESSENGER.TELEGRAM.value]  # type: ignore
    bot_token: str
    chat_id: str


class Config(BaseModel, use_enum_values=True, extra=Extra.forbid):
    database: Database
    stockists: list[Stockist]
    messengers: dict[
        str, Annotated[Union[Discord, Telegram], Field(discriminator="messenger_type")]
    ]
    scrape_interval: int = 600
    notify_first_run: bool = False

    @validator("scrape_interval")
    def interval_amount(cls, v):
        if v < 600:
            raise ValueError("Scraping interval lower limit is 300 (10 mins)")
        return v


def load_config(path):
    if not path.is_file():
        raise ValueError(f"{path} does not exist")
    else:
        f = open(path)
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"ERROR: Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}"
            )

        try:
            return Config(**data)
        except ValidationError as e:
            raise ValueError(f"{e}")
