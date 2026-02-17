import json
import logging
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    IPvAnyAddress,
    ValidationError,
    field_validator,
)
from typing_extensions import Annotated

log = logging.getLogger(__name__)


class Databases(Enum):
    POSTGRES = "postgres"
    SQLITE = "sqlite"


class MESSENGER(Enum):
    DISCORD = "discord"
    TELEGRAM = "telegram"


class Stockist(Enum):
    BESTBUY = "bestbuy.com"
    BESTBUYCA = "bestbuy.ca"
    CEXUK = "uk.webuy.com"
    GAMESTOP = "gamestop.com"
    GAMEUK = "game.co.uk"
    MECCHAJAPAN = "meccha-japan.com"
    NINTENDOUK = "nintendo.co.uk"
    PLAYASIA = "play-asia.com"
    SHOPTO = "shopto.net"
    THESOURCE = "thesource.ca"


class Database(BaseModel, use_enum_values=True, extra="forbid"):
    engine: str = Databases.SQLITE  # type: ignore
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str | IPvAnyAddress] = "127.0.0.1"
    port: Optional[int] = Field(5432, ge=1, le=65535)
    name: str = "amiiboalert"


class Discord(BaseModel, use_enum_values=True, extra="forbid"):
    active: bool = False
    embedded_messages: bool = True
    messenger_type: Literal[MESSENGER.DISCORD.value]  # type: ignore
    webhook_url: HttpUrl
    stockists: list[Stockist]

    @field_validator("stockists")
    @classmethod
    def validate_stockists_not_empty(cls, v: list[Stockist]) -> list[Stockist]:
        """Ensure at least one stockist is configured."""
        if not v:
            raise ValueError(
                "Discord messenger must have at least one stockist configured"
            )
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate webhook URL is a valid Discord webhook."""
        url_str = str(v)
        if (
            "discord.com/api/webhooks" not in url_str
            and "discordapp.com/api/webhooks" not in url_str
        ):
            log.warning(f"Discord webhook URL may be invalid: {url_str}")
        return v


class Telegram(BaseModel, use_enum_values=True, extra="forbid"):
    active: bool = False
    embedded_messages: bool = True
    messenger_type: Literal[MESSENGER.TELEGRAM.value]  # type: ignore
    bot_token: str
    chat_id: str
    stockists: list[Stockist]

    @field_validator("stockists")
    @classmethod
    def validate_stockists_not_empty(cls, v: list[Stockist]) -> list[Stockist]:
        """Ensure at least one stockist is configured."""
        if not v:
            raise ValueError(
                "Telegram messenger must have at least one stockist configured"
            )
        return v

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate bot token format."""
        if not v or len(v) < 10:
            raise ValueError("Telegram bot token appears to be invalid (too short)")
        return v

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, v: str) -> str:
        """Validate chat ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Telegram chat_id cannot be empty")
        return v


class Config(BaseModel, use_enum_values=True, extra="forbid"):
    database: Database
    messengers: dict[
        str, Annotated[Union[Discord, Telegram], Field(discriminator="messenger_type")]
    ]

    @field_validator("messengers")
    @classmethod
    def validate_messengers_not_empty(cls, v: dict) -> dict:
        """Ensure at least one messenger is configured."""
        if not v:
            raise ValueError("At least one messenger must be configured")
        return v


def load_config(path):
    """Load and validate configuration from JSON file.

    Args:
        path: Path object pointing to config.json

    Returns:
        Validated Config object

    Raises:
        ValueError: If config file is invalid or missing
    """
    if not path.is_file():
        raise ValueError(f"{path} does not exist")

    with open(path) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"ERROR: Invalid JSON: {exc.msg}, line {exc.lineno}, column {exc.colno}"
            )

    try:
        config = Config(**data)
        log.info("Configuration validated successfully")
        return config
    except ValidationError as e:
        error_details = "\n".join(
            [
                f"  - {error['msg']} at {'.'.join(str(x) for x in error['loc'])}"
                for error in e.errors()
            ]
        )
        raise ValueError(f"Configuration validation failed:\n{error_details}")
