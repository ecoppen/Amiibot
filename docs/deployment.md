# Scheduling

Amiibot does one check and exits, so something else has to run it repeatedly. Every 10 minutes is a reasonable interval. A run with several browser-based shops can take a few minutes, and hammering the shops more often than that is more likely to get you blocked than to get you alerts any sooner. If a run is still going when the next one starts, the new one logs "Another instance is already running" and exits, so overlap is harmless.

Both examples below assume Amiibot is in `/home/you/Amiibot` and you've already run `uv sync` there. They call the virtualenv's Python directly, because cron and systemd often don't have `uv` on their `PATH`. The working directory matters: the config, database, log file and lock file are all looked up relative to it.

## Cron

```
*/10 * * * * cd /home/you/Amiibot && .venv/bin/python amiibot.py >> cron.log 2>&1
```

Add it with `crontab -e`. `log.txt` already has everything and rotates itself, but `cron.log` doesn't, and it's the only place a crash before logging starts (a missing dependency, say) would show up.

## systemd timer

Because the script exits after each run, the service should be `Type=oneshot` and a timer should start it. Don't use `Type=simple` with `Restart=on-failure`: exit code 2 just means a shop failed that time, and systemd would keep restarting it.

`/etc/systemd/system/amiibot.service`:

```ini
[Unit]
Description=Amiibot stock check
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=you
WorkingDirectory=/home/you/Amiibot
ExecStart=/home/you/Amiibot/.venv/bin/python amiibot.py
SuccessExitStatus=2
```

`SuccessExitStatus=2` stops systemd marking the unit as failed when only some shops failed. Drop it if you'd like to see those runs flagged.

`/etc/systemd/system/amiibot.timer`:

```ini
[Unit]
Description=Run Amiibot every 10 minutes

[Timer]
OnBootSec=2min
OnUnitInactiveSec=10min

[Install]
WantedBy=timers.target
```

`OnUnitInactiveSec` counts from when the previous run finished, which also keeps runs from stacking up. Enable it with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now amiibot.timer
```

Check on it with `systemctl list-timers amiibot.timer` and read the output of the last run with `journalctl -u amiibot -n 50`.

## Looking after it

Your config contains webhook URLs and possibly a database password, so `chmod 600 config/config.json` is sensible. The logs redact webhook tokens, bot tokens and chat IDs.

The database is Amiibot's memory. If you lose it, the next run treats every product as new and alerts on all of them, so it's worth copying `amiibot.db` somewhere now and then (`pg_dump` for Postgres). Don't delete old rows to tidy up for the same reason. Nothing in Amiibot prunes the database, and it grows slowly.

To update:

```bash
cd /home/you/Amiibot
git pull
uv sync
```

Database changes are applied automatically at the start of the next run, so there's no migration step.
