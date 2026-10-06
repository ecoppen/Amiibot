# Troubleshooting

Start with `log.txt` (or the console, or `journalctl -u amiibot` if you use the systemd timer). Setting `LOGLEVEL=DEBUG` for one run gives you more detail.

## "config/config.json does not exist"

You're either not in the Amiibot directory or you haven't copied the example config yet. The path is relative to wherever you run the script from, so check your cron line or `WorkingDirectory=` has the right directory.

## "Configuration validation failed"

Amiibot exits with code 1 and tells you which field is wrong. The usual suspects are the placeholder webhook URL left in from `config.example.json`, an empty `stockists` list, a stockist value that isn't one of the supported ones, a Telegram token that doesn't look like `123456789:AA...`, and a stray trailing comma in the JSON. [Configuration](configuration.md) has the details.

## "Another instance is already running"

Amiibot holds a lock on `.amiibot.lock` while it runs, and a second copy exits straight away with code 1. Most of the time this is fine: the previous run is still going. If it keeps happening, check what's running with `pgrep -af amiibot.py`. A leftover `.amiibot.lock` file on its own does nothing, because the lock is released when the process dies, so you never need to delete it.

## No items returned, or exit code 2

You'll see `No items returned from <shop>` in the log, and the run exits with 2. Amiibot deliberately does nothing with an empty result, so you won't get false delisting alerts, but you also won't get alerts for that shop until it works again. Likely causes:

- The shop changed its page layout and the scraper needs updating. If a shop has been empty for days, this is it, and an issue on GitHub is welcome.
- The shop is blocking you or timing out. Requests give up after 5 seconds (`REQUEST_TIMEOUT` in `constants.py`), and a timeout or HTTP error is logged as a warning and counts as an empty result.
- It's a Selenium shop and Chrome isn't working (next section).

## Selenium or Chrome errors

You'll see `WebDriver exception` or `Selenium timeout` in the log. Several shops (Best Buy, GameStop, GAME, ShopTo, The Source, Play-Asia and Meccha Japan, in some cases only as a fallback) need a real browser. Install Chrome or Chromium on the machine and make sure you can launch it. Selenium downloads a matching driver the first time it's needed, which needs internet access and a writable home directory for the user running Amiibot.

On a Raspberry Pi or other ARM Linux box that automatic download often doesn't work. Install the browser and driver from your distro instead, which is usually `chromium` and `chromium-driver` on Debian-based systems (the package names vary).

## Discord rate limiting

`<name> is rate limited; deferring remaining notifications` means Discord returned a 429. The alerts aren't lost. They stay queued and go out on the next run, as long as that's within 24 hours and five attempts. This normally only happens when a lot of alerts go out at once, such as the first run against a new shop. If you've set `DISCORD_WEBHOOK_URL`, remember it points every Discord messenger at the same webhook, which makes it more likely.

## Alerts aren't arriving

Work through these in order:

1. Is the messenger `"active": true`? An inactive one scrapes but never sends.
2. Is it a Telegram messenger? Telegram alerts aren't currently delivered (see the note in [Configuration](configuration.md)).
3. Did the run log `Queued N notification(s)`? If not, nothing changed, or the change was inside the 60-minute cooldown (the log says `cooldown`).
4. If it queued some, look at what happened to them:

    ```bash
    sqlite3 amiibot.db "SELECT title, stock_status, messenger_name, delivery_status FROM notification_deliveries ORDER BY id DESC LIMIT 10;"
    ```

    `permanent_failure` means Discord rejected the message, usually because the webhook was deleted or the URL is wrong. `transient_failure` means it'll be retried.

## Everything was announced as new again

Amiibot lost track of what it had seen. The database name is a path relative to the working directory, so running it from a different directory, or changing `name` in the config, starts a new empty database and the first run alerts on every product. Go back to the original directory and name, or restore the old `.db` file.

## Database errors

For SQLite, make sure the user running Amiibot can write to the `.db` file and the directory it's in. For Postgres, check the credentials and that the server is up (`psql -h 127.0.0.1 -U amiibot amiibot`).

Tables are created and upgraded automatically at the start of every run. If you get an error about a missing column right after an update, the upgrade probably couldn't run, most often because the Postgres user isn't allowed to alter the tables or the SQLite file is read-only. Fix the permissions and run it again.
