"""
Unit tests for configuration module.
"""

import json
import tempfile
from pathlib import Path

import pytest

from config.config import load_config


class TestConfiguration:
    """Test configuration loading and validation."""

    def test_load_config_sqlite(self):
        """Test loading SQLite configuration."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "test_discord": {
                    "messenger_type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": ["bestbuy.com"],
                }
            },
        }

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert config is not None
            assert config.database.engine == "sqlite"
            assert config.database.name == "test_db"
        finally:
            temp_path.unlink()

    def test_load_config_postgres(self):
        """Test loading PostgreSQL configuration."""
        config_data = {
            "database": {
                "engine": "postgres",
                "username": "test_user",
                "password": "test_pass",
                "host": "localhost",
                "port": 5432,
                "name": "test_db",
            },
            "messengers": {
                "test_telegram": {
                    "messenger_type": "telegram",
                    "bot_token": "1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
                    "chat_id": "123456789",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": ["gamestop.com"],
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert config is not None
            assert config.database.engine == "postgres"
            assert config.database.username == "test_user"
        finally:
            temp_path.unlink()

    def test_load_config_file_not_found(self):
        """Test loading non-existent config file."""
        with pytest.raises(ValueError, match="does not exist"):
            load_config(Path("nonexistent.json"))

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_config(temp_path)
        finally:
            temp_path.unlink()

    def test_config_validation_empty_stockists(self):
        """Test configuration validation with empty stockists list."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "test_discord": {
                    "messenger_type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": [],  # Empty list
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="at least one stockist"):
                load_config(temp_path)
        finally:
            temp_path.unlink()

    def test_config_validation_invalid_telegram_token(self):
        """Test configuration validation with invalid Telegram token."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "test_telegram": {
                    "messenger_type": "telegram",
                    "bot_token": "short",  # Too short
                    "chat_id": "123456789",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": ["bestbuy.com"],
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="bot token"):
                load_config(temp_path)
        finally:
            temp_path.unlink()

    def test_config_validation_empty_messengers(self):
        """Test configuration validation with empty messengers."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {},  # Empty
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="At least one messenger"):
                load_config(temp_path)
        finally:
            temp_path.unlink()

    def test_database_sqlite_defaults(self):
        """Test SQLite database with default values."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "test": {
                    "messenger_type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": ["bestbuy.com"],
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert config.database.engine == "sqlite"
            assert config.database.name == "test_db"
        finally:
            temp_path.unlink()

    def test_messenger_active_false(self):
        """Test messenger with active=false."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "inactive_discord": {
                    "messenger_type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "active": False,
                    "embedded_messages": True,
                    "stockists": ["bestbuy.com"],
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert config.messengers["inactive_discord"].active is False
        finally:
            temp_path.unlink()

    def test_multiple_messengers(self):
        """Test configuration with multiple messengers."""
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "discord1": {
                    "messenger_type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/111/aaa",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": ["bestbuy.com"],
                },
                "telegram1": {
                    "messenger_type": "telegram",
                    "bot_token": "1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
                    "chat_id": "123456789",
                    "active": True,
                    "embedded_messages": True,
                    "stockists": ["gamestop.com"],
                },
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = load_config(temp_path)
            assert len(config.messengers) == 2
            assert "discord1" in config.messengers
            assert "telegram1" in config.messengers
        finally:
            temp_path.unlink()

    def test_stockist_enum_values(self):
        """Test stockist enum values."""
        from config.config import Stockist

        # Test that common stockists are available
        assert "bestbuy.com" in [s.value for s in Stockist]
        assert "gamestop.com" in [s.value for s in Stockist]
        assert "nintendo.co.uk" in [s.value for s in Stockist]

    def test_messenger_enum_values(self):
        """Test messenger enum values."""
        from config.config import MESSENGER

        assert MESSENGER.DISCORD.value == "discord"
        assert MESSENGER.TELEGRAM.value == "telegram"

    def test_databases_enum_values(self):
        """Test databases enum values."""
        from config.config import Databases

        assert Databases.SQLITE.value == "sqlite"
        assert Databases.POSTGRES.value == "postgres"


class TestDiscordMention:
    """Validation of the optional Discord mention."""

    @staticmethod
    def _config(**extra):
        from config.config import DiscordMessengerConfig

        return DiscordMessengerConfig(
            messenger_type="discord",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            stockists=["nintendo.co.uk"],
            **extra,
        )

    def test_default_is_none(self):
        assert self._config().mention is None

    @pytest.mark.parametrize(
        "value",
        ["@here", "@everyone", "<@&123456789012345678>", "<@123456789012345678>"],
    )
    def test_valid_mentions(self, value):
        assert self._config(mention=value).mention == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "here",
            "@Here",
            "@role",
            "<@&abc>",
            "<@&>",
            "<@>",
            "<@!123>",
            "<#123>",
            "123456",
            "<@&123> <@&456>",
            "<@&123>\n",
            " @here",
        ],
    )
    def test_invalid_mentions(self, value):
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc:
            self._config(mention=value)
        assert "mention must be" in str(exc.value)

    def test_mention_loads_from_file(self):
        config_data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": {
                "d": {
                    "messenger_type": "discord",
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                    "active": True,
                    "stockists": ["bestbuy.com"],
                    "mention": "<@&42>",
                }
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)
        try:
            config = load_config(temp_path)
            assert config.messengers["d"].mention == "<@&42>"
        finally:
            temp_path.unlink()


REMOVED_SHOPS = ["game.co.uk", "thesource.ca", "meccha-japan.com"]


class TestRemovedStockists:
    """Shops that are no longer scraped stay loadable but are ignored."""

    TELEGRAM_TOKEN = "123456789:" + "A" * 35

    @classmethod
    def _messenger(cls, kind, stockists):
        if kind == "discord":
            return {
                "messenger_type": "discord",
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "active": True,
                "stockists": stockists,
            }
        return {
            "messenger_type": "telegram",
            "bot_token": cls.TELEGRAM_TOKEN,
            "chat_id": "42",
            "active": True,
            "stockists": stockists,
        }

    @staticmethod
    def _load(messengers):
        data = {
            "database": {"engine": "sqlite", "name": "test_db"},
            "messengers": messengers,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = Path(f.name)
        try:
            return load_config(temp_path)
        finally:
            temp_path.unlink()

    def test_removed_values_stay_in_the_enum(self):
        from config.config import REMOVED_STOCKISTS, Stockist

        values = {s.value for s in Stockist}
        assert set(REMOVED_SHOPS) == set(REMOVED_STOCKISTS)
        assert set(REMOVED_SHOPS) <= values

    @pytest.mark.parametrize("kind", ["discord", "telegram"])
    @pytest.mark.parametrize("removed", REMOVED_SHOPS)
    def test_removed_stockist_is_dropped_with_a_warning(self, kind, removed, caplog):
        with caplog.at_level("WARNING", logger="config.config"):
            config = self._load(
                {"m": self._messenger(kind, ["nintendo.co.uk", removed])}
            )

        assert config.messengers["m"].stockists == ["nintendo.co.uk"]
        assert (
            f"{removed} is no longer supported and is ignored; "
            "remove it from config.json"
        ) in caplog.text

    def test_all_removed_values_are_dropped_and_each_is_reported(self, caplog):
        with caplog.at_level("WARNING", logger="config.config"):
            config = self._load(
                {"m": self._messenger("discord", ["shopto.net", *REMOVED_SHOPS])}
            )

        assert config.messengers["m"].stockists == ["shopto.net"]
        for removed in REMOVED_SHOPS:
            assert f"{removed} is no longer supported" in caplog.text

    @pytest.mark.parametrize("kind", ["discord", "telegram"])
    def test_only_removed_stockists_is_a_clear_error(self, kind):
        with pytest.raises(ValueError) as exc:
            self._load({"m": self._messenger(kind, ["game.co.uk", "thesource.ca"])})

        message = str(exc.value)
        assert "no supported stockist left" in message
        assert "game.co.uk, thesource.ca are no longer supported" in message

    def test_single_removed_stockist_error_reads_correctly(self):
        with pytest.raises(
            ValueError, match=r"meccha-japan.com is no longer supported"
        ):
            self._load({"m": self._messenger("discord", ["meccha-japan.com"])})

    @pytest.mark.parametrize("kind", ["discord", "telegram"])
    def test_empty_list_still_gives_the_original_error(self, kind):
        with pytest.raises(ValueError, match="at least one stockist"):
            self._load({"m": self._messenger(kind, [])})

    def test_supported_stockists_are_untouched_and_quiet(self, caplog):
        with caplog.at_level("WARNING", logger="config.config"):
            config = self._load(
                {"m": self._messenger("discord", ["bestbuy.com", "play-asia.com"])}
            )

        assert config.messengers["m"].stockists == ["bestbuy.com", "play-asia.com"]
        assert "no longer supported" not in caplog.text

    def test_unknown_stockist_is_still_rejected(self):
        with pytest.raises(ValueError, match="Configuration validation failed"):
            self._load({"m": self._messenger("discord", ["not-a-shop.com"])})
