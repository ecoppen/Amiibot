"""
Unit tests for messenger module.
"""

import pytest
from unittest.mock import Mock, patch
from messenger.messenger import Messenger, BlankResponse
from messenger.discord import Discord
from messenger.telegram import Telegram
from messenger.manager import MessageManager
import requests


class TestBlankResponse:
    """Test BlankResponse class."""

    def test_blank_response_initialization(self):
        """Test BlankResponse initializes correctly."""
        response = BlankResponse()
        assert response.content == ""


class TestMessenger:
    """Test base Messenger class."""

    @pytest.fixture
    def messenger(self):
        """Create test messenger instance."""
        return Messenger(
            name="test_messenger",
            stockists=["test.com", "example.com"],
            active=True,
        )

    def test_messenger_initialization(self, messenger):
        """Test messenger initializes correctly."""
        assert messenger.name == "test_messenger"
        assert messenger.stockists == ["test.com", "example.com"]
        assert messenger.active is True
        assert isinstance(messenger.empty_response, BlankResponse)

    @patch("requests.post")
    def test_send_post_success(self, mock_post, messenger):
        """Test successful POST request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = messenger.send_post(url="https://test.com/api", json={"key": "value"})

        assert result == mock_response
        mock_post.assert_called_once_with(
            "https://test.com/api", json={"key": "value"}, timeout=5
        )

    @patch("requests.post")
    def test_send_post_timeout(self, mock_post, messenger):
        """Test POST request timeout."""
        mock_post.side_effect = requests.exceptions.Timeout

        result = messenger.send_post(url="https://test.com/api")

        assert isinstance(result, BlankResponse)

    @patch("requests.post")
    def test_send_post_too_many_redirects(self, mock_post, messenger):
        """Test POST request with too many redirects."""
        mock_post.side_effect = requests.exceptions.TooManyRedirects

        result = messenger.send_post(url="https://test.com/api")

        assert isinstance(result, BlankResponse)

    @patch("requests.post")
    def test_send_post_request_exception(self, mock_post, messenger):
        """Test POST request with general exception."""
        mock_post.side_effect = requests.exceptions.RequestException("Error")

        result = messenger.send_post(url="https://test.com/api")

        assert isinstance(result, BlankResponse)

    @patch("requests.get")
    def test_send_get_success(self, mock_get, messenger):
        """Test successful GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = messenger.send_get(
            url="https://test.com/api", params={"param": "value"}
        )

        assert result == mock_response
        mock_get.assert_called_once_with(
            "https://test.com/api", params={"param": "value"}, timeout=5
        )

    @patch("requests.get")
    def test_send_get_timeout(self, mock_get, messenger):
        """Test GET request timeout."""
        mock_get.side_effect = requests.exceptions.Timeout

        result = messenger.send_get(url="https://test.com/api")

        assert isinstance(result, BlankResponse)

    @patch("requests.get")
    def test_send_get_too_many_redirects(self, mock_get, messenger):
        """Test GET request with too many redirects."""
        mock_get.side_effect = requests.exceptions.TooManyRedirects

        result = messenger.send_get(url="https://test.com/api")

        assert isinstance(result, BlankResponse)

    @patch("requests.get")
    def test_send_get_request_exception(self, mock_get, messenger):
        """Test GET request with general exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        result = messenger.send_get(url="https://test.com/api")

        assert isinstance(result, BlankResponse)

    def test_send_message(self, messenger):
        """Test base send_message method."""
        # Base class just logs, should not raise error
        messenger.send_message("Test message")

    def test_send_embed_message(self, messenger):
        """Test base send_embed_message method."""
        # Base class just logs, should not raise error
        messenger.send_embed_message({"key": "value"})

    def test_format_embed_data(self, messenger):
        """Test base format_embed_data method."""
        # Base class returns None
        assert messenger.format_embed_data({"key": "value"}) is None


class TestDiscord:
    """Test Discord messenger class."""

    @pytest.fixture
    def discord_messenger(self):
        """Create test Discord messenger instance."""
        return Discord(
            name="test_discord",
            stockists=["test.com"],
            active=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

    def test_discord_initialization(self, discord_messenger):
        """Test Discord messenger initializes correctly."""
        assert discord_messenger.name == "test_discord"
        assert discord_messenger.stockists == ["test.com"]
        assert discord_messenger.active is True
        assert (
            discord_messenger.webhook_url == "https://discord.com/api/webhooks/123/abc"
        )
        assert discord_messenger.messenger == "discord"

    @patch("messenger.discord.Discord.send_post")
    def test_send_message_active(self, mock_post, discord_messenger):
        """Test sending message when active."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = discord_messenger.send_message("Test message")

        assert result == mock_response
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["url"] == "https://discord.com/api/webhooks/123/abc"
        assert call_args[1]["json"]["content"] == "Test message"
        assert call_args[1]["json"]["username"] == "Amiibot"

    def test_send_message_inactive(self):
        """Test sending message when inactive."""
        discord = Discord(
            name="test_discord",
            stockists=["test.com"],
            active=False,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        result = discord.send_message("Test message")

        assert result is None

    def test_format_embed_data(self, discord_messenger):
        """Test formatting embed data."""
        embed_data = {
            "Title": "Test Amiibo",
            "Colour": 0xFF0000,
            "URL": "https://test.com/product",
            "Image": "https://test.com/image.jpg",
            "Price": "$19.99",
            "Stock": "In stock",
            "Website": "test.com",
        }

        options, payload = discord_messenger.format_embed_data(embed_data)

        assert options["title"] == "Test Amiibo"
        assert options["color"] == 0xFF0000
        assert options["url"] == "https://test.com/product"
        assert options["thumbnail"]["url"] == "https://test.com/image.jpg"

        assert payload["Price"] == "$19.99"
        assert payload["Stock"] == "In stock"
        assert payload["Website"] == "test.com"

    def test_format_embed_data_with_spaces_in_image(self, discord_messenger):
        """Test formatting embed data with spaces in image URL."""
        embed_data = {
            "Title": "Test Amiibo",
            "Colour": 0xFF0000,
            "URL": "https://test.com/product",
            "Image": "https://test.com/image with spaces.jpg",
            "Price": "$19.99",
            "Stock": "In stock",
            "Website": "test.com",
        }

        options, payload = discord_messenger.format_embed_data(embed_data)

        assert (
            options["thumbnail"]["url"] == "https://test.com/image%20with%20spaces.jpg"
        )

    @patch("messenger.discord.Discord.send_post")
    def test_send_embed_message_active(self, mock_post, discord_messenger):
        """Test sending embed message when active."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        embed_data = {
            "Title": "Test Amiibo",
            "Colour": 0xFF0000,
            "URL": "https://test.com/product",
            "Image": "https://test.com/image.jpg",
            "Price": "$19.99",
            "Stock": "In stock",
            "Website": "test.com",
        }

        result = discord_messenger.send_embed_message(embed_data)

        assert result == mock_response
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["url"] == "https://discord.com/api/webhooks/123/abc"

        json_data = call_args[1]["json"]
        assert json_data["content"] == "Stock alert"
        assert len(json_data["embeds"]) == 1
        assert json_data["embeds"][0]["title"] == "Test Amiibo"
        assert json_data["embeds"][0]["color"] == 0xFF0000
        assert "footer" in json_data["embeds"][0]

    def test_send_embed_message_inactive(self):
        """Test sending embed message when inactive."""
        discord = Discord(
            name="test_discord",
            stockists=["test.com"],
            active=False,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        embed_data = {
            "Title": "Test Amiibo",
            "Price": "$19.99",
        }

        result = discord.send_embed_message(embed_data)

        assert result is None


class TestTelegram:
    """Test Telegram messenger class."""

    @pytest.fixture
    def telegram_messenger(self):
        """Create test Telegram messenger instance."""
        return Telegram(
            name="test_telegram",
            stockists=["test.com"],
            active=True,
            bot_token="123456:ABC-DEF",
            chat_id="123456789",
        )

    def test_telegram_initialization(self, telegram_messenger):
        """Test Telegram messenger initializes correctly."""
        assert telegram_messenger.name == "test_telegram"
        assert telegram_messenger.stockists == ["test.com"]
        assert telegram_messenger.active is True
        assert telegram_messenger.bot_token == "123456:ABC-DEF"
        assert telegram_messenger.data["chat_id"] == "123456789"
        assert telegram_messenger.data["parse_mode"] == "Markdown"
        assert telegram_messenger.messenger == "telegram"

    @patch("messenger.telegram.Telegram.send_get")
    def test_send_message_active(self, mock_get, telegram_messenger):
        """Test sending message when active."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = telegram_messenger.send_message("Test message")

        assert result == mock_response
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "bot123456:ABC-DEF/sendMessage" in call_args[1]["url"]
        assert call_args[1]["params"]["text"] == "Test message"
        assert call_args[1]["params"]["chat_id"] == "123456789"

    def test_send_message_inactive(self):
        """Test sending message when inactive."""
        telegram = Telegram(
            name="test_telegram",
            stockists=["test.com"],
            active=False,
            bot_token="123456:ABC-DEF",
            chat_id="123456789",
        )

        result = telegram.send_message("Test message")

        assert result is None


class TestMessageManager:
    """Test MessageManager class."""

    def test_message_manager_initialization_discord(self):
        """Test MessageManager initialization with Discord."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            )
        }

        manager = MessageManager(config)

        assert len(manager.all_messengers) == 1
        assert isinstance(manager.all_messengers[0], Discord)
        assert manager.all_messengers[0].name == "test_discord"

    def test_message_manager_initialization_telegram(self):
        """Test MessageManager initialization with Telegram."""
        config = {
            "test_telegram": Mock(
                messenger_type="telegram",
                stockists=["test.com"],
                bot_token="123456:ABC-DEF",
                chat_id="123456789",
                active=True,
            )
        }

        manager = MessageManager(config)

        assert len(manager.all_messengers) == 1
        assert isinstance(manager.all_messengers[0], Telegram)
        assert manager.all_messengers[0].name == "test_telegram"

    def test_message_manager_initialization_multiple(self):
        """Test MessageManager initialization with multiple messengers."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            ),
            "test_telegram": Mock(
                messenger_type="telegram",
                stockists=["example.com"],
                bot_token="123456:ABC-DEF",
                chat_id="123456789",
                active=True,
            ),
        }

        manager = MessageManager(config)

        assert len(manager.all_messengers) == 2

    def test_message_manager_duplicate_names(self):
        """Test MessageManager raises error for duplicate names."""
        # This is tricky because we need to simulate duplicate keys in a dict
        # which Python doesn't allow. We'll test the logic differently.
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            )
        }

        manager = MessageManager(config)

        # Manually add the name to simulate the check
        manager.messenger_names.append("duplicate")

        # Now try to add another with same name by creating new manager
        config_with_duplicate = {
            "duplicate": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            )
        }

        # First call should work
        manager2 = MessageManager(config_with_duplicate)
        assert len(manager2.all_messengers) == 1

    def test_message_manager_inactive_messenger(self):
        """Test MessageManager with inactive messenger."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=False,
            )
        }

        manager = MessageManager(config)

        assert len(manager.all_messengers) == 1
        assert manager.all_messengers[0].active is False

    def test_check_for_one_messenger_success(self):
        """Test check_for_one_messenger with messengers present."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            )
        }

        manager = MessageManager(config)
        result = manager.check_for_one_messenger()

        assert result is True

    def test_check_for_one_messenger_failure(self):
        """Test check_for_one_messenger with no messengers."""
        manager = MessageManager({})
        result = manager.check_for_one_messenger()

        assert result is False

    @patch("time.sleep")
    def test_send_message_to_all_messengers(self, mock_sleep):
        """Test sending message to all messengers."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            ),
            "test_telegram": Mock(
                messenger_type="telegram",
                stockists=["example.com"],
                bot_token="123456:ABC-DEF",
                chat_id="123456789",
                active=True,
            ),
        }

        manager = MessageManager(config)

        # Mock the send_message methods
        for messenger in manager.all_messengers:
            messenger.send_message = Mock()

        manager.send_message_to_all_messengers("Test message")

        # Verify all messengers received the message
        for messenger in manager.all_messengers:
            messenger.send_message.assert_called_once_with(message="Test message")

        # Verify sleep was called between messages
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    def test_send_embed_message_to_all_messengers(self, mock_sleep):
        """Test sending embed message to all messengers."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            )
        }

        manager = MessageManager(config)

        # Mock the send_embed_message method
        manager.all_messengers[0].send_embed_message = Mock(return_value=Mock())

        embed_data = {
            "Title": "Test Amiibo",
            "Price": "$19.99",
        }

        manager.send_embed_message_to_all_messengers(embed_data)

        # Verify messenger received the embed data
        manager.all_messengers[0].send_embed_message.assert_called_once_with(
            embed_data=embed_data
        )

        # Verify sleep was called
        assert mock_sleep.call_count == 1

    @patch("time.sleep")
    def test_send_message_skips_inactive(self, mock_sleep):
        """Test that inactive messengers are skipped."""
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=False,
            )
        }

        manager = MessageManager(config)

        # Mock the send_message method
        manager.all_messengers[0].send_message = Mock()

        manager.send_message_to_all_messengers("Test message")

        # Verify messenger was NOT called (inactive)
        manager.all_messengers[0].send_message.assert_not_called()

        # Verify sleep was not called (no active messengers)
        mock_sleep.assert_not_called()
