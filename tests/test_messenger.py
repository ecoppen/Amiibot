import pytest
from unittest.mock import Mock, patch
from messenger.messenger import Messenger
from messenger.discord import Discord
from messenger.telegram import Telegram
from messenger.manager import MessageManager
from result import DeliveryResult, DeliveryStatus
import requests


class TestMessenger:
    @pytest.fixture
    def messenger(self):
        return Messenger(
            name="test_messenger",
            stockists=["test.com", "example.com"],
            active=True,
        )

    def test_messenger_initialization(self, messenger):
        assert messenger.name == "test_messenger"
        assert messenger.stockists == ["test.com", "example.com"]
        assert messenger.active is True

    @patch("requests.post")
    def test_send_post_success(self, mock_post, messenger):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = messenger.send_post(url="https://test.com/api", json={"key": "value"})

        assert isinstance(result, DeliveryResult)
        assert result.status == DeliveryStatus.SUCCESS
        assert result.http_status == 200

    @patch("requests.post")
    def test_send_post_timeout(self, mock_post, messenger):
        mock_post.side_effect = requests.exceptions.Timeout

        result = messenger.send_post(url="https://test.com/api")

        assert result.status == DeliveryStatus.TRANSIENT_FAILURE
        assert result.diagnostic == "timeout"

    @patch("requests.post")
    def test_send_post_too_many_redirects(self, mock_post, messenger):
        mock_post.side_effect = requests.exceptions.TooManyRedirects

        result = messenger.send_post(url="https://test.com/api")

        assert result.status == DeliveryStatus.PERMANENT_FAILURE

    @patch("requests.post")
    def test_send_post_request_exception(self, mock_post, messenger):
        mock_post.side_effect = requests.exceptions.RequestException("Error")

        result = messenger.send_post(url="https://test.com/api")

        assert result.status == DeliveryStatus.TRANSIENT_FAILURE

    @patch("requests.post")
    def test_send_post_4xx_permanent_failure(self, mock_post, messenger):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        result = messenger.send_post(url="https://test.com/api")

        assert result.status == DeliveryStatus.PERMANENT_FAILURE
        assert result.http_status == 403

    @patch("requests.post")
    def test_send_post_5xx_transient(self, mock_post, messenger):
        mock_response = Mock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response

        result = messenger.send_post(url="https://test.com/api")

        assert result.status == DeliveryStatus.TRANSIENT_FAILURE
        assert result.http_status == 503

    @patch("requests.post")
    def test_send_post_429_transient(self, mock_post, messenger):
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        result = messenger.send_post(url="https://test.com/api")

        assert result.status == DeliveryStatus.TRANSIENT_FAILURE
        assert result.http_status == 429

    @patch("requests.get")
    def test_send_get_success(self, mock_get, messenger):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = messenger.send_get(
            url="https://test.com/api", params={"param": "value"}
        )

        assert result.status == DeliveryStatus.SUCCESS
        assert result.http_status == 200

    @patch("requests.get")
    def test_send_get_timeout(self, mock_get, messenger):
        mock_get.side_effect = requests.exceptions.Timeout

        result = messenger.send_get(url="https://test.com/api")

        assert result.status == DeliveryStatus.TRANSIENT_FAILURE

    @patch("requests.get")
    def test_send_get_too_many_redirects(self, mock_get, messenger):
        mock_get.side_effect = requests.exceptions.TooManyRedirects

        result = messenger.send_get(url="https://test.com/api")

        assert result.status == DeliveryStatus.PERMANENT_FAILURE

    @patch("requests.get")
    def test_send_get_request_exception(self, mock_get, messenger):
        mock_get.side_effect = requests.exceptions.RequestException("Error")

        result = messenger.send_get(url="https://test.com/api")

        assert result.status == DeliveryStatus.TRANSIENT_FAILURE

    def test_send_message(self, messenger):
        result = messenger.send_message("Test message")
        assert isinstance(result, DeliveryResult)
        assert result.status == DeliveryStatus.INACTIVE

    def test_send_embed_message(self, messenger):
        result = messenger.send_embed_message({"key": "value"})
        assert isinstance(result, DeliveryResult)
        assert result.status == DeliveryStatus.INACTIVE


class TestDiscord:
    @pytest.fixture
    def discord_messenger(self):
        return Discord(
            name="test_discord",
            stockists=["test.com"],
            active=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

    def test_discord_initialization(self, discord_messenger):
        assert discord_messenger.name == "test_discord"
        assert discord_messenger.stockists == ["test.com"]
        assert discord_messenger.active is True
        assert (
            discord_messenger.webhook_url == "https://discord.com/api/webhooks/123/abc"
        )
        assert discord_messenger.messenger == "discord"

    @patch("messenger.discord.Discord.send_post")
    def test_send_message_active(self, mock_post, discord_messenger):
        mock_post.return_value = DeliveryResult(
            status=DeliveryStatus.SUCCESS,
            messenger_name="test_discord",
            http_status=200,
        )

        result = discord_messenger.send_message("Test message")

        assert result.status == DeliveryStatus.SUCCESS
        mock_post.assert_called_once()

    def test_send_message_inactive(self):
        discord = Discord(
            name="test_discord",
            stockists=["test.com"],
            active=False,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        result = discord.send_message("Test message")

        assert result.status == DeliveryStatus.INACTIVE

    @patch("messenger.discord.Discord.send_post")
    def test_send_embed_message_active(self, mock_post, discord_messenger):
        mock_post.return_value = DeliveryResult(
            status=DeliveryStatus.SUCCESS,
            messenger_name="test_discord",
            http_status=200,
        )

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

        assert result.status == DeliveryStatus.SUCCESS

    def test_send_embed_message_inactive(self):
        discord = Discord(
            name="test_discord",
            stockists=["test.com"],
            active=False,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        result = discord.send_embed_message({"Title": "Test", "Price": "$19.99"})

        assert result.status == DeliveryStatus.INACTIVE


class TestTelegram:
    @pytest.fixture
    def telegram_messenger(self):
        return Telegram(
            name="test_telegram",
            stockists=["test.com"],
            active=True,
            bot_token="1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
            chat_id="123456789",
        )

    def test_telegram_initialization(self, telegram_messenger):
        assert telegram_messenger.name == "test_telegram"
        assert telegram_messenger.stockists == ["test.com"]
        assert telegram_messenger.active is True
        assert (
            telegram_messenger.bot_token
            == "1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs"
        )
        assert telegram_messenger.data["chat_id"] == "123456789"

    @patch("messenger.telegram.Telegram.send_get")
    def test_send_message_active(self, mock_get, telegram_messenger):
        mock_get.return_value = DeliveryResult(
            status=DeliveryStatus.SUCCESS,
            messenger_name="test_telegram",
            http_status=200,
        )

        result = telegram_messenger.send_message("Test message")

        assert result.status == DeliveryStatus.SUCCESS
        mock_get.assert_called_once()

    def test_send_message_inactive(self):
        telegram = Telegram(
            name="test_telegram",
            stockists=["test.com"],
            active=False,
            bot_token="1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
            chat_id="123456789",
        )

        result = telegram.send_message("Test message")

        assert result.status == DeliveryStatus.INACTIVE


class TestMessageManager:
    def test_message_manager_initialization_discord(self):
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
        config = {
            "test_telegram": Mock(
                messenger_type="telegram",
                stockists=["test.com"],
                bot_token="1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
                chat_id="123456789",
                active=True,
            )
        }
        manager = MessageManager(config)
        assert len(manager.all_messengers) == 1
        assert isinstance(manager.all_messengers[0], Telegram)

    def test_message_manager_initialization_multiple(self):
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
                bot_token="1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
                chat_id="123456789",
                active=True,
            ),
        }
        manager = MessageManager(config)
        assert len(manager.all_messengers) == 2

    def test_check_for_one_messenger_success(self):
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
        manager = MessageManager({})
        result = manager.check_for_one_messenger()
        assert result is False

    @patch("time.sleep")
    def test_send_message_to_all_messengers(self, mock_sleep):
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
                bot_token="1234567890:AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxs",
                chat_id="123456789",
                active=True,
            ),
        }
        manager = MessageManager(config)
        for messenger in manager.all_messengers:
            messenger.send_message = Mock()
        manager.send_message_to_all_messengers("Test message")
        for messenger in manager.all_messengers:
            messenger.send_message.assert_called_once_with(message="Test message")
        assert mock_sleep.call_count == 2

    @patch("time.sleep")
    def test_send_embed_message_to_all_messengers(self, mock_sleep):
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=True,
            )
        }
        manager = MessageManager(config)
        manager.all_messengers[0].send_embed_message = Mock(
            return_value=DeliveryResult(
                status=DeliveryStatus.SUCCESS, messenger_name="test_discord"
            )
        )
        embed_data = {"Title": "Test Amiibo", "Price": "$19.99"}
        manager.send_embed_message_to_all_messengers(embed_data)
        manager.all_messengers[0].send_embed_message.assert_called_once_with(
            embed_data=embed_data
        )
        assert mock_sleep.call_count == 1

    @patch("time.sleep")
    def test_send_message_skips_inactive(self, mock_sleep):
        config = {
            "test_discord": Mock(
                messenger_type="discord",
                stockists=["test.com"],
                webhook_url="https://discord.com/api/webhooks/123/abc",
                active=False,
            )
        }
        manager = MessageManager(config)
        manager.all_messengers[0].send_message = Mock()
        manager.send_message_to_all_messengers("Test message")
        manager.all_messengers[0].send_message.assert_not_called()
        mock_sleep.assert_not_called()
