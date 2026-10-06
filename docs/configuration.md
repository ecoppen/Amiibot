# Configuration

Everything lives in `config/config.json`, relative to the directory you run Amiibot from. The file is validated when the script starts, and unknown keys are rejected, so a typo in a field name is an error rather than being silently ignored. There are two top-level keys: `database` and `messengers`.

## Database

SQLite is the default and is all most people need:

```json
"database": { "engine": "sqlite", "name": "amiibot" }
```

This creates `amiibot.db` in the current directory. `name` is the filename without `.db`. If you leave it out it defaults to `amiiboalert`, which is a leftover from the project's earlier name, so set it explicitly.

For Postgres:

```json
"database": {
  "engine": "postgres",
  "username": "amiibot",
  "password": "change-me",
  "host": "127.0.0.1",
  "port": 5432,
  "name": "amiibot"
}
```

`host` defaults to `127.0.0.1` and `port` to `5432`. The user needs to own (or at least be able to create and alter tables in) the database, since Amiibot creates and upgrades its own tables on startup:

```bash
sudo -u postgres createuser --pwprompt amiibot
sudo -u postgres createdb --owner amiibot amiibot
```

You can keep the password out of the file with the `DATABASE_PASSWORD` environment variable.

## Messengers

`messengers` is an object where each key is a name you choose and each value is a Discord or Telegram messenger. You can have as many as you like, each watching a different set of shops.

### Discord

```json
"uk_alerts": {
  "messenger_type": "discord",
  "webhook_url": "https://discord.com/api/webhooks/123456789/your-token",
  "active": true,
  "stockists": ["nintendo.co.uk", "bestbuy.ca", "shopto.net"]
}
```

The webhook URL has to be an `https://discord.com/api/webhooks/<numeric id>/<token>` (or `discordapp.com`) URL. To make one, open the channel's settings in Discord, go to Integrations, then Webhooks, and create a new webhook. Each alert is posted as an embed with the product name, link, thumbnail, price, stock status and shop.

#### Mentions

To get pinged for the alerts that matter most, add an optional `mention` to the messenger:

```json
"uk_alerts": {
  "messenger_type": "discord",
  "webhook_url": "https://discord.com/api/webhooks/123456789/your-token",
  "active": true,
  "mention": "<@&123456789012345678>",
  "stockists": ["nintendo.co.uk"]
}
```

It has to be one of these:

| Value | Pings |
|-------|-------|
| `@here` | Everyone online in the channel. |
| `@everyone` | Everyone in the channel. |
| `<@&ROLE_ID>` | A role. |
| `<@USER_ID>` | One person. |

Only "In stock" and "Pre-order" alerts ping. Every other message, including the [failure and recovery messages](alerts.md#when-a-shop-keeps-failing), never does, even if the text happens to contain a mention.

To find a role ID, turn on Developer Mode in Discord (User Settings, Advanced), then right-click the role in the server settings, choose Copy Role ID, and write it as `<@&` followed by the ID and `>`. For a person, right-click their name and choose Copy User ID, and write it as `<@` followed by the ID and `>`. If a role ping doesn't fire, check that the role is set to be mentionable in the server settings.

### Telegram

```json
"telegram_alerts": {
  "messenger_type": "telegram",
  "bot_token": "123456789:AAExampleTokenFromBotFatherxxxxxxxxx",
  "chat_id": "987654321",
  "active": true,
  "stockists": ["nintendo.co.uk"]
}
```

Create a bot by messaging @BotFather and sending `/newbot`. Your chat ID is the number @userinfobot replies with; for a group it's negative. Send your bot `/start` once so it's allowed to message you. The token has to look like a real one (8 to 12 digits, a colon, then 30 to 50 letters, digits, underscores or hyphens) or validation fails.

### Common fields

| Field | Default | Notes |
|-------|---------|-------|
| `messenger_type` | none | `discord` or `telegram`. |
| `active` | `false` | Set to `true` or the messenger never sends anything. |
| `stockists` | none | At least one entry from the table below. |
| `embedded_messages` | `true` | Accepted for compatibility but currently not used by anything. Discord always sends embeds. |

An inactive messenger still counts when working out which shops to scrape, so a shop that is only listed under inactive messengers is scraped for no reason.

## Stockists

| Shop | Value | Country |
|------|-------|---------|
| GameStop | `gamestop.com` | 🇺🇸 |
| Best Buy Canada | `bestbuy.ca` | 🇨🇦 |
| Nintendo UK | `nintendo.co.uk` | 🇬🇧 |
| ShopTo | `shopto.net` | 🇬🇧 |
| CeX | `uk.webuy.com` | 🇬🇧 |
| Play-Asia | `play-asia.com` | ships internationally |

### Removed shops

Four shops are no longer supported because they stopped working: Best Buy US (`bestbuy.com`, it serves an empty product list to automated browsers behind bot detection and reCAPTCHA, so it can't be scraped reliably), GAME (`game.co.uk`, the amiibo page is gone), The Source (`thesource.ca`, the site has closed and redirects to Best Buy) and Meccha Japan (`meccha-japan.com`, it now puts an "I'm not a robot" check in front of every page). They are not scraped any more. Best Buy US could come back through Best Buy's official Products API, which needs a free developer key.

If one of them is still in your `config.json` the config still loads. Amiibot ignores it and writes a warning such as "game.co.uk is no longer supported and is ignored; remove it from config.json" to the log. It's worth deleting the entry to silence the warning. If a messenger has nothing but removed shops in its list, the config is rejected with an error saying so, because that messenger would have nothing to watch.

Adding a shop that isn't in the table means writing a scraper for it: subclass `Stockist` in `stockist/`, register it in `STOCKIST_FACTORY` in `stockist/manager.py`, and add its value to the `Stockist` enum in `config/config.py`.

## Environment variables

These override the file after it has been validated, so the file still needs values that look valid (a well-formed webhook URL, a token in the right format). They're useful for keeping secrets out of the JSON.

| Variable | Effect |
|----------|--------|
| `DATABASE_PASSWORD` | Replaces `database.password`. |
| `DISCORD_WEBHOOK_URL` | Replaces the webhook URL of **every** Discord messenger. |
| `TELEGRAM_BOT_TOKEN` | Replaces the bot token of every Telegram messenger. |
| `TELEGRAM_CHAT_ID` | Replaces the chat ID of every Telegram messenger. |
| `LOGLEVEL` | Log level, `INFO` by default. |

The Discord one catches people out. If you have two Discord messengers pointing at different channels and set `DISCORD_WEBHOOK_URL`, both end up posting to that one webhook. Use it only if you have a single Discord messenger.

## Validation errors

If the config is wrong the script prints the problem and exits with code 1 before scraping anything. Each error ends with the path of the offending field:

```
Configuration validation failed:
  - Value error, Discord messenger must have at least one stockist configured at messengers.uk_alerts.discord.stockists
```

The usual causes are an empty `stockists` list, a stockist value that isn't in the table above, a webhook URL that doesn't match the format described earlier (the placeholder in `config.example.json` is one), a missing `bot_token` or `chat_id`, and invalid JSON such as a trailing comma.
