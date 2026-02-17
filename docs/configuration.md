# Configuration Guide

Complete reference for all Amiibot configuration options.

---

## Configuration File Structure

Amiibot uses a JSON configuration file located at `config/config.json`. The configuration is validated using Pydantic for type safety and clear error messages.

```json
{
  "database": { ... },
  "messengers": { ... }
}
```

---

## Database Configuration

### SQLite (Default)

Perfect for personal use and getting started.

```json
{
  "database": {
    "engine": "sqlite",
    "name": "amiibot"
  }
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `engine` | string | Yes | `"sqlite"` | Database engine type |
| `name` | string | Yes | `"amiibot"` | Database file name (without .db extension) |

---

### PostgreSQL

Recommended for production and multi-instance deployments.

```json
{
  "database": {
    "engine": "postgres",
    "username": "amiibot_user",
    "password": "secure_password",
    "host": "localhost",
    "port": 5432,
    "name": "amiibot"
  }
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `engine` | string | Yes | - | Must be `"postgres"` |
| `username` | string | Yes | - | PostgreSQL username |
| `password` | string | Yes | - | PostgreSQL password |
| `host` | string | No | `"127.0.0.1"` | PostgreSQL server IP/hostname |
| `port` | integer | No | `5432` | PostgreSQL server port (1-65535) |
| `name` | string | Yes | `"amiibot"` | Database name |

**Advantages:**
- ✅ Better for production
- ✅ Supports multiple instances
- ✅ Better concurrent access
- ✅ Advanced features

**Setup:**

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb amiibot

# Create user
sudo -u postgres psql
CREATE USER amiibot_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE amiibot TO amiibot_user;
\q
```

---

## Messenger Configuration

You can configure multiple messengers with different stockist lists. Each messenger must have a unique name.

### Discord Webhook

```json
{
  "messengers": {
    "discord_us": {
      "messenger_type": "discord",
      "webhook_url": "https://discord.com/api/webhooks/123456/abcdef",
      "active": true,
      "embedded_messages": true,
      "stockists": ["bestbuy.com", "gamestop.com"]
    }
  }
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `messenger_type` | string | Yes | - | Must be `"discord"` |
| `webhook_url` | URL | Yes | - | Discord webhook URL |
| `active` | boolean | Yes | `false` | Enable/disable notifications |
| `embedded_messages` | boolean | Yes | `true` | Use rich embeds (recommended) |
| `stockists` | array | Yes | - | List of stockist URLs to track |

**Getting a Discord Webhook:**

1. Open Discord and go to your server
2. Right-click the channel → Edit Channel
3. Go to Integrations → Webhooks
4. Click "New Webhook" or "Create Webhook"
5. Give it a name and avatar (optional)
6. Copy the webhook URL

!!! tip "Multiple Discord Webhooks"
    You can create multiple webhooks for different channels:

    ```json
    {
      "messengers": {
        "discord_us": {
          "messenger_type": "discord",
          "webhook_url": "https://discord.com/api/webhooks/111/aaa",
          "active": true,
          "embedded_messages": true,
          "stockists": ["bestbuy.com"]
        },
        "discord_uk": {
          "messenger_type": "discord",
          "webhook_url": "https://discord.com/api/webhooks/222/bbb",
          "active": true,
          "embedded_messages": true,
          "stockists": ["nintendo.co.uk"]
        }
      }
    }
    ```

---

### Telegram Bot

```json
{
  "messengers": {
    "telegram_main": {
      "messenger_type": "telegram",
      "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
      "chat_id": "123456789",
      "active": true,
      "embedded_messages": true,
      "stockists": ["nintendo.co.uk", "game.co.uk"]
    }
  }
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `messenger_type` | string | Yes | - | Must be `"telegram"` |
| `bot_token` | string | Yes | - | Telegram bot API token |
| `chat_id` | string | Yes | - | Telegram chat ID |
| `active` | boolean | Yes | `false` | Enable/disable notifications |
| `embedded_messages` | boolean | Yes | `true` | Use formatted messages |
| `stockists` | array | Yes | - | List of stockist URLs to track |

**Setting up a Telegram Bot:**

1. **Create Bot:**
   - Open Telegram and search for @BotFather
   - Send `/newbot`
   - Follow the instructions to choose a name and username
   - Copy the bot token

2. **Get Chat ID:**
   - Send `/start` to @userinfobot
   - It will respond with your user ID (this is your chat_id)

   **OR** for group chats:
   - Add your bot to the group
   - Add @userinfobot to the group
   - Your chat ID will be shown (starts with -)

3. **Start conversation:**
   - Send `/start` to your bot
   - Now it can send you messages

---

## Stockists Configuration

Each messenger can track different stockists. Available stockists:

### North America

| Stockist | Code | Country |
|----------|------|---------|
| Best Buy | `bestbuy.com` | 🇺🇸 USA |
| GameStop | `gamestop.com` | 🇺🇸 USA |
| Best Buy CA | `bestbuy.ca` | 🇨🇦 Canada |
| The Source | `thesource.ca` | 🇨🇦 Canada |

### Europe

| Stockist | Code | Country |
|----------|------|---------|
| Nintendo UK | `nintendo.co.uk` | 🇬🇧 UK |
| GAME | `game.co.uk` | 🇬🇧 UK |
| ShopTo | `shopto.net` | 🇬🇧 UK |
| CeX | `uk.webuy.com` | 🇬🇧 UK |

### Asia

| Stockist | Code | Country |
|----------|------|---------|
| Play-Asia | `play-asia.com` | 🌏 Asia |
| Meccha Japan | `meccha-japan.com` | 🇯🇵 Japan |

**Example Configuration:**

```json
{
  "messengers": {
    "all_regions": {
      "messenger_type": "discord",
      "webhook_url": "YOUR_WEBHOOK_URL",
      "active": true,
      "embedded_messages": true,
      "stockists": [
        "bestbuy.com",
        "gamestop.com",
        "nintendo.co.uk",
        "game.co.uk",
        "play-asia.com"
      ]
    }
  }
}
```

!!! warning "Stockist List Validation"
    The stockists list must contain at least one valid stockist URL. The configuration will fail validation if the list is empty or contains invalid URLs.

---

## Complete Example

Here's a complete configuration example with multiple messengers and databases:

=== "Production (PostgreSQL + Multiple Messengers)"

    ```json
    {
      "database": {
        "engine": "postgres",
        "username": "amiibot_user",
        "password": "secure_password_here",
        "host": "localhost",
        "port": 5432,
        "name": "amiibot"
      },
      "messengers": {
        "discord_us_general": {
          "messenger_type": "discord",
          "webhook_url": "https://discord.com/api/webhooks/111/aaa",
          "active": true,
          "embedded_messages": true,
          "stockists": ["bestbuy.com", "gamestop.com"]
        },
        "discord_uk_general": {
          "messenger_type": "discord",
          "webhook_url": "https://discord.com/api/webhooks/222/bbb",
          "active": true,
          "embedded_messages": true,
          "stockists": ["nintendo.co.uk", "game.co.uk", "shopto.net"]
        },
        "telegram_alerts": {
          "messenger_type": "telegram",
          "bot_token": "123456:ABC-DEF",
          "chat_id": "987654321",
          "active": true,
          "embedded_messages": true,
          "stockists": ["play-asia.com", "meccha-japan.com"]
        }
      }
    }
    ```

=== "Development (SQLite + Single Messenger)"

    ```json
    {
      "database": {
        "engine": "sqlite",
        "name": "amiibot_dev"
      },
      "messengers": {
        "discord_test": {
          "messenger_type": "discord",
          "webhook_url": "https://discord.com/api/webhooks/TEST/test",
          "active": true,
          "embedded_messages": true,
          "stockists": ["bestbuy.com"]
        }
      }
    }
    ```

---

## Configuration Validation

Amiibot validates your configuration at startup. Common validation errors:

### Empty Stockists List

```
Configuration validation failed:
  - Discord messenger must have at least one stockist configured at messengers.discord_main.stockists
```

**Fix:** Add at least one stockist to the list.

### Invalid Webhook URL

```
Configuration validation failed:
  - Invalid Discord webhook URL at messengers.discord_main.webhook_url
```

**Fix:** Ensure the webhook URL contains `discord.com/api/webhooks/`.

### Missing Required Fields

```
Configuration validation failed:
  - Missing required field: bot_token at messengers.telegram_main
```

**Fix:** Add the missing field to your configuration.

---

## Environment Variables

For sensitive data, you can use environment variables (requires code modification):

```python
import os

config = {
    "database": {
        "password": os.getenv("DB_PASSWORD", "default_password")
    }
}
```
