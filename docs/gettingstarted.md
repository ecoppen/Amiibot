# Getting started

Amiibot checks amiibo stock at a set of shops and sends you a message when something changes. It isn't a long-running service. Each time you run it, it scrapes every shop in your config once, queues and sends any alerts, and exits. To keep watching, you run it on a schedule (see [Scheduling](deployment.md)).

## What you need

Python 3.13 or newer, [uv](https://docs.astral.sh/uv/), and Chrome or Chromium. Most shops are scraped with plain HTTP requests, but a few fall back to headless Chrome through Selenium when the page needs JavaScript. Postgres is optional; SQLite is fine for home use.

## Install

```bash
git clone https://github.com/ecoppen/Amiibot.git
cd Amiibot
uv sync
```

`uv sync` creates `.venv` and installs the dependencies. If you'd rather not use uv, create a virtualenv and `pip install` the packages listed under `dependencies` in `pyproject.toml`.

## Configure

```bash
cp config/config.example.json config/config.json
```

The example's webhook URL is a placeholder and will fail validation, so you have to edit it. A minimal config looks like this:

```json
{
  "database": { "engine": "sqlite", "name": "amiibot" },
  "messengers": {
    "my_discord": {
      "messenger_type": "discord",
      "webhook_url": "https://discord.com/api/webhooks/123456789/your-token",
      "active": true,
      "stockists": ["nintendo.co.uk", "shopto.net"]
    }
  }
}
```

To get a webhook URL, open the channel settings in Discord, go to Integrations, then Webhooks, and create one. Every option, the list of shops and the environment variable overrides are covered in [Configuration](configuration.md).

## Run it

```bash
uv run amiibot.py
```

Run it from the repository directory. The config path, the SQLite file, `log.txt` and the lock file are all relative to the current directory, and running from somewhere else gives you a fresh, empty database (and a flood of "new" alerts).

The first run alerts on every product it finds. After that you only get alerts for changes, as described in [How alerts work](alerts.md). The last line of the output is a summary:

```
Run summary: status=SUCCESS exit=0 stockists=2/2 notifications=0
```

`amiibot_runner.sh` does the same thing from `~/Amiibot` if you want something to point cron at.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Every stockist was scraped. |
| 2 | Some stockists failed or returned nothing. The others were still processed. |
| 3 | The scrape cycle crashed. |
| 1 | Fatal error: bad config, database problem, or another run holds the lock. |
| 130 | Interrupted with Ctrl-C. |

## Logs

The console output is human-readable. `log.txt` is JSON lines and rotates at 5MB, keeping five old files. Pass `--log-json` to get JSON on the console as well, and set `LOGLEVEL=DEBUG` for more detail.

```bash
tail -f log.txt | jq -r '[.ts, .level, .message] | join(" ")'
```

## Check the database

SQLite stores everything in `<name>.db` (so `amiibot.db` with the config above):

```bash
sqlite3 amiibot.db "SELECT Website, COUNT(*) FROM amiibo_stock GROUP BY Website;"
```
