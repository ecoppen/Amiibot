<p align="center">
  <a href="https://ecoppen.github.io/amiibot/">
    <img src="https://raw.githubusercontent.com/ecoppen/Amiibot/main/docs/amiibot.png" width="200" alt="Amiibot">
  </a>
</p>

<h1 align="center">Amiibot</h1>

<p align="center">
Amiibo stock checker and notifier for Discord and Telegram
</p>

<p align="center">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
<a href="https://www.python.org/downloads/"><img alt="Python 3.13+" src="https://img.shields.io/badge/python-3.13+-blue.svg"></a>
<a href="https://codecov.io/gh/ecoppen/Amiibot"><img alt="codecov" src="https://codecov.io/gh/ecoppen/Amiibot/branch/main/graph/badge.svg"></a>
</p>

Amiibot checks a handful of UK, US, Canadian and Asian shops for amiibo and pings you on Discord when something appears, sells out, comes back, changes price or disappears. It's a small Python script, not a service: each run does one check of every shop you've configured and exits, so you run it from cron or a systemd timer. State lives in a local SQLite database (or Postgres if you prefer).

## Quick start

You need Python 3.13, [uv](https://docs.astral.sh/uv/) and Chrome or Chromium (some shops need a real browser).

```bash
git clone https://github.com/ecoppen/Amiibot.git
cd Amiibot
uv sync
cp config/config.example.json config/config.json
```

Put your Discord webhook URL and the shops you care about in `config/config.json`, then:

```bash
uv run amiibot.py
```

The first run alerts on every product it finds, so expect a burst of messages. After that you only hear about changes.

Full docs, including scheduling and troubleshooting, are at https://ecoppen.github.io/amiibot/.
