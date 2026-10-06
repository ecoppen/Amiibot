# How alerts work

Amiibot remembers every product it has seen at each shop, and on every run it compares what it finds against that memory. You get an alert when:

- a product shows up that it hasn't seen before
- a product goes from out of stock to in stock, or the other way round
- a product goes on pre-order, or moves from pre-order to in stock or out of stock
- the price changes while the stock status stays the same (if both change you get a single stock alert carrying the new price)
- a product has gone missing from the shop's listing (a delisting)
- a delisted product comes back

The first run against a shop alerts on every product it finds, in stock or not. That includes a shop you add to the config later. If you delete the database, the same thing happens again.

## Pre-orders

A pre-order is a product you can order before it is released. It gets its own "Pre-order" status, with an orange embed, so it isn't mistaken for a restock. Nintendo UK, Best Buy Canada, GameStop and Play-Asia report pre-orders. Best Buy (US), ShopTo and CeX don't tell Amiibot the difference, so a pre-order there will look like any other status.

When the shop gives a release date that is today or later, the alert has an extra "Release" field, for example "12 Nov 2026". Nintendo UK, Best Buy Canada and GameStop give release dates; Play-Asia doesn't. The date is only shown in the alert. It is not remembered between runs, and a changed release date on its own doesn't trigger a new alert.

If Nintendo UK reports a status Amiibot doesn't recognise, it is treated as out of stock and a warning is written to the log.

A pre-order that has sold out is reported as out of stock, and keeps its release date. Best Buy Canada's search results don't say what is in stock, so Amiibot makes a second request to its availability service. If that request fails, the run still works but treats every listed item as in stock (or on pre-order), and a warning is written to the log.

## Delisting

A product only counts as delisted after it has been missing from `SCRAPING_FAILURE_GRACE_PERIOD` runs in a row (2 by default), and you're told once. If it reappears you get an alert with its current stock status.

Because a broken scrape can look exactly like a shop emptying its shelves, there are some guards. A scrape that returns nothing is treated as a failure, changes nothing in the database, and makes the run exit with code 2. A scrape that returns less than half of what that shop usually has (`STOCKIST_HEALTH_RATIO`) doesn't trigger any delistings. If it's low twice in a row (`CONSECUTIVE_UNHEALTHY_THRESHOLD`) the lower number becomes the new normal and delistings resume.

## When a shop keeps failing

Amiibot can also tell you when a shop has stopped working. If a shop fails `STOCKIST_FAILURE_ALERT_THRESHOLD` runs in a row (6 by default, about an hour at a 10-minute schedule), it sends a plain text message to that shop's messengers, along the lines of:

> Amiibot: Nintendo UK has failed 6 runs in a row (last error: ...). Alerts for it are paused until it recovers.

A failed run is one that raised an error or came back with nothing usable. If there was no error, the message says "returned no items". You only get this message once per streak. If no messenger manages to deliver it, for example because Discord is down, it is tried again on the next run.

When the shop works again you get one more message, such as "Amiibot: Nintendo UK is working again after 7 failed runs." You only get it if the failure message was sent.

These messages skip the outbox and the cooldown and never ping anyone. The recovery message is not retried if it fails to send. A problem sending either message is logged and the run carries on.

## Delivery

Alerts aren't sent straight away. When a change is detected it's written to a `notification_outbox` table in the same database transaction as the change itself, so a crash can't leave you with a recorded change and no alert. At the end of each shop's scrape the pending alerts for that shop are sent.

If a send fails with a timeout, a 5xx or a 429 it's tried again on later runs, and given up on after `OUTBOX_MAX_AGE_HOURS` (24) or `OUTBOX_MAX_ATTEMPTS` (5), whichever comes first. Other failures, such as a deleted webhook, aren't retried. Each alert is only sent once per messenger, so a retry won't duplicate it for a messenger that already got it.

Sends are spaced `MESSAGE_SEND_DELAY` seconds apart (0.5). If Discord answers 429, that messenger is paused for the rest of the run and its remaining alerts wait for the next one.

## Cooldown

To stop an item that's flapping from spamming you, a repeat alert of the same kind for the same item is suppressed for `NOTIFICATION_COOLDOWN_MINUTES` (60) after the last one was sent. The exceptions are "In stock" and "Pre-order" alerts, which are never suppressed. The change itself is still recorded, so the next alert compares against the up-to-date state.

## Tuning

The thresholds above are constants in `constants.py`. There's no config option for them, so edit the file and they apply from the next run. `REQUEST_TIMEOUT` (5 seconds) is there too, and is the one to raise if a slow shop keeps coming back empty.
