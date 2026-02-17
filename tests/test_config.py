"""
Unit tests for configuration module.
"""

import pytest
import json
import tempfile
from pathlib import Path
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
                    "bot_token": "123456:ABC-DEF",
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
                    "bot_token": "123456:ABC-DEF",
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
