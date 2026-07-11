import json
import logging
import os
import re
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import (
    BaseModel,
    Field,
    IPvAnyAddress,
    ValidationError,
    field_validator,
)

log = logging.getLogger(__name__)

_SECRET_REDACT = "***"

REDACTION_PATTERNS = [
    (re.compile(r"(bot\d+:[A-Za-z0-9_-]+)"), _SECRET_REDACT),
    (re.compile(r"(api/webhooks/\d+/)[A-Za-z0-9_-]+"), r"\1***"),
    (re.compile(r"chat_id=\d+"), "chat_id=***"),
]


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


def _env_or_fallback(env_var: str, config_value: str | None, name: str) -> str | None:
    env_val = os.environ.get(env_var)
    if env_val:
        return env_val
    return config_value


def _redact(value: str) -> str:
    for pattern, replacement in REDACTION_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


class DatabaseConfig(BaseModel, use_enum_values=True, extra="forbid"):
    engine: str = Databases.SQLITE  # type: ignore
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str | IPvAnyAddress] = "127.0.0.1"
    port: Optional[int] = Field(5432, ge=1, le=65535)
    name: str = "amiiboalert"

    def resolve_secrets(self) -> None:
        if env_pass := os.environ.get("DATABASE_PASSWORD"):
            self.password = env_pass


class DiscordMessengerConfig(BaseModel, use_enum_values=True, extra="forbid"):
    active: bool = False
    embedded_messages: bool = True
    messenger_type: Literal[MESSENGER.DISCORD.value]  # type: ignore
    webhook_url: str
    stockists: list[Stockist]

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        parsed = v.split("/")
        if len(parsed) < 6:
            raise ValueError("Invalid Discord webhook URL format")
        host_part = parsed[2] if len(parsed) > 2 else ""
        if host_part not in ("discord.com", "discordapp.com"):
            raise ValueError(
                f"Expected discord.com or discordapp.com host, got: {host_part}"
            )
        if not v.startswith("https://"):
            raise ValueError("Discord webhook URL must use HTTPS")
        path_parts = v.split("/")[3:]
        if len(path_parts) < 4 or path_parts[0] != "api" or path_parts[1] != "webhooks":
            raise ValueError("Discord webhook URL must contain /api/webhooks/ path")
        try:
            int(path_parts[2])
        except ValueError:
            raise ValueError("Discord webhook ID must be a numeric value")
        if not path_parts[3]:
            raise ValueError("Discord webhook token cannot be empty")
        return v

    @field_validator("stockists")
    @classmethod
    def validate_stockists_not_empty(cls, v: list[Stockist]) -> list[Stockist]:
        if not v:
            raise ValueError(
                "Discord messenger must have at least one stockist configured"
            )
        return v

    def resolve_secrets(self) -> None:
        if env_url := os.environ.get("DISCORD_WEBHOOK_URL"):
            self.webhook_url = env_url


class TelegramMessengerConfig(BaseModel, use_enum_values=True, extra="forbid"):
    active: bool = False
    embedded_messages: bool = True
    messenger_type: Literal[MESSENGER.TELEGRAM.value]  # type: ignore
    bot_token: str
    chat_id: str
    stockists: list[Stockist]

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        if not re.match(r"^\d{8,12}:[A-Za-z0-9_-]{30,50}$", v):
            raise ValueError(
                "Telegram bot token must match format: <numeric>:<alphanumeric>"
            )
        return v

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Telegram chat_id cannot be empty")
        return v

    @field_validator("stockists")
    @classmethod
    def validate_stockists_not_empty(cls, v: list[Stockist]) -> list[Stockist]:
        if not v:
            raise ValueError(
                "Telegram messenger must have at least one stockist configured"
            )
        return v

    def resolve_secrets(self) -> None:
        if env_token := os.environ.get("TELEGRAM_BOT_TOKEN"):
            self.bot_token = env_token
        if env_chat := os.environ.get("TELEGRAM_CHAT_ID"):
            self.chat_id = env_chat


class Config(BaseModel, use_enum_values=True, extra="forbid"):
    database: DatabaseConfig
    messengers: dict[
        str,
        Annotated[
            Union[DiscordMessengerConfig, TelegramMessengerConfig],
            Field(discriminator="messenger_type"),
        ],
    ]

    @field_validator("messengers")
    @classmethod
    def validate_messengers_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("At least one messenger must be configured")
        return v

    def resolve_secrets(self) -> None:
        self.database.resolve_secrets()
        for messenger in self.messengers.values():
            messenger.resolve_secrets()


def load_config(path):
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
        config.resolve_secrets()
        log.info("Configuration loaded and validated successfully")
        return config
    except ValidationError as e:
        error_details = "\n".join(
            f"  - {error['msg']} at {'.'.join(str(x) for x in error['loc'])}"
            for error in e.errors()
        )
        raise ValueError(f"Configuration validation failed:\n{error_details}")


def redact_secrets(text: str) -> str:
    return _redact(text)
