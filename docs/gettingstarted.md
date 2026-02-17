# Getting Started

Amiibot is a production-ready web scraper and stock notifier for Amiibo. Track multiple retailers and get notified instantly when stock changes occur (`In stock`, `Out of stock`, `Price change`).

## 🎯 Quick Start

```bash
# Clone the repository
git clone https://github.com/ecoppen/Amiibot.git
cd Amiibot

# Install dependencies
uv sync

# Configure the bot
cp config/config.example.json config/config.json
# Edit config/config.json with your settings

# Run the bot
python amiibot.py
```

---

## 📋 Requirements

### Hardware Requirements

**Minimum:**
- 512MB RAM
- 1GB disk space
- Network connection

**Recommended:**
- 1GB+ RAM
- 5GB+ disk space
- Stable internet connection
- 24/7 availability

### Supported Platforms

- ✅ Linux (Ubuntu, Debian, CentOS, etc.)
- ✅ macOS (10.15+)
- ✅ Windows (10/11)
- ✅ Raspberry Pi (3B+ or newer)

### Software Requirements

**Required:**
- Python 3.12 or higher
- uv (package manager)
- Chrome/Chromium (for Selenium)

**Optional:**
- PostgreSQL (for production)
- systemd (for service management)
- cron (for scheduling)

---

## 📦 Installation

### Method 1: Using uv (Recommended)

uv is the fastest and most reliable way to install Amiibot.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/ecoppen/Amiibot.git
cd Amiibot

# Install dependencies
uv sync

# The virtual environment is automatically created at .venv/
```

### Method 2: Using pip

```bash
# Clone the repository
git clone https://github.com/ecoppen/Amiibot.git
cd Amiibot

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

### Method 3: Development Installation

For contributors and developers:

```bash
# Clone the repository
git clone https://github.com/ecoppen/Amiibot.git
cd Amiibot

# Install with development dependencies
uv sync --group dev

# Install pre-commit hooks
pre-commit install
```

---

## ⚙️ Configuration

### Step 1: Create Configuration File

```bash
cd config
cp config.example.json config.json
```

### Step 2: Basic Configuration

Edit `config/config.json` with your favorite editor:

```bash
nano config/config.json  # or vim, code, etc.
```

Minimal configuration example:

```json
{
  "database": {
    "engine": "sqlite",
    "name": "amiibot"
  },
  "messengers": {
    "my_discord": {
      "messenger_type": "discord",
      "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE",
      "active": true,
      "embedded_messages": true,
      "stockists": ["bestbuy.com", "gamestop.com"]
    }
  }
}
```

!!! tip "Configuration Validation"
    Amiibot validates your configuration at startup and will show clear error messages if something is wrong.

### Step 3: Database Setup

=== "SQLite (Easiest)"

    No additional setup required! Just specify in config:

    ```json
    {
      "database": {
        "engine": "sqlite",
        "name": "amiibot"
      }
    }
    ```

=== "PostgreSQL (Production)"

    ```bash
    # Install PostgreSQL
    sudo apt install postgresql postgresql-contrib

    # Create database
    sudo -u postgres createdb amiibot

    # Create user (optional)
    sudo -u postgres createuser amiibot_user
    ```

    Configuration:

    ```json
    {
      "database": {
        "engine": "postgres",
        "username": "amiibot_user",
        "password": "your_password",
        "host": "localhost",
        "port": 5432,
        "name": "amiibot"
      }
    }
    ```

### Step 4: Messenger Setup

=== "Discord"

    1. Go to your Discord server
    2. Server Settings → Integrations → Webhooks
    3. Click "New Webhook"
    4. Choose a channel and copy the webhook URL
    5. Add to configuration:

    ```json
    {
      "messengers": {
        "discord_main": {
          "messenger_type": "discord",
          "webhook_url": "YOUR_WEBHOOK_URL_HERE",
          "active": true,
          "embedded_messages": true,
          "stockists": ["bestbuy.com"]
        }
      }
    }
    ```

=== "Telegram"

    1. Message @BotFather on Telegram
    2. Send `/newbot` and follow instructions
    3. Copy the bot token
    4. Send `/start` to @userinfobot to get your chat ID
    5. Add to configuration:

    ```json
    {
      "messengers": {
        "telegram_main": {
          "messenger_type": "telegram",
          "bot_token": "YOUR_BOT_TOKEN",
          "chat_id": "YOUR_CHAT_ID",
          "active": true,
          "embedded_messages": true,
          "stockists": ["nintendo.co.uk"]
        }
      }
    }
    ```

!!! info "Multiple Messengers"
    You can configure multiple Discord and Telegram messengers with different stockist lists!

---

## 🚀 Running the Bot

### Manual Execution

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate  # Windows

# Run the bot
python amiibot.py
```

You should see output like:

```
2026-02-17 10:00:00 - root - INFO - config/config.json loaded
2026-02-17 10:00:00 - root - INFO - sqlite loaded
2026-02-17 10:00:00 - root - INFO - database tables loaded
2026-02-17 10:00:00 - root - INFO - discord_main setup to send messages to Discord
2026-02-17 10:00:00 - root - INFO - Now tracking bestbuy.com
2026-02-17 10:00:00 - root - INFO - Now scraping 1 site(s): Best Buy US
2026-02-17 10:00:00 - root - INFO - Starting scraper...
```

### Scheduled Execution (Cron)

For automatic execution every 30 minutes:

```bash
# Edit crontab
crontab -e

# Add this line
*/30 * * * * cd /path/to/Amiibot && /path/to/Amiibot/.venv/bin/python amiibot.py >> /path/to/Amiibot/cron.log 2>&1
```

!!! tip "Finding Python Path"
    ```bash
    cd /path/to/Amiibot
    source .venv/bin/activate
    which python  # Copy this path for crontab
    ```

### Using the Runner Script

The repository includes a convenient runner script:

```bash
# Make it executable
chmod +x amiibot_runner.sh

# Run it
./amiibot_runner.sh
```

---

## 🔍 Verification

### Check Logs

```bash
# View recent logs
tail -f log.txt

# View log with timestamps
cat log.txt
```

### Check Database

```bash
# For SQLite
sqlite3 amiibot.db "SELECT COUNT(*) FROM amiibo_stock;"

# For PostgreSQL
psql -U amiibot_user -d amiibot -c "SELECT COUNT(*) FROM amiibo_stock;"
```

### Test Notification

After first run, you should receive notifications for any amiibo currently in stock!

---
