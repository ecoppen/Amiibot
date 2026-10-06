# How alerts work

Amiibot remembers every product it has seen at each shop, and on every run it compares what it finds against that memory. You get an alert when:

- a product shows up that it hasn't seen before
- a product goes from out of stock to in stock, or the other way round
- the price changes while the stock status stays the same (if both change you get a single stock alert carrying the new price)
- a product has gone missing from the shop's listing (a delisting)
- a delisted product comes back

The first run against a shop alerts on every product it finds, in stock or not. That includes a shop you add to the config later. If you delete the database, the same thing happens again.

## Delisting

A product only counts as delisted after it has been missing from `SCRAPING_FAILURE_GRACE_PERIOD` runs in a row (2 by default), and you're told once. If it reappears you get an alert with its current stock status.

Because a broken scrape can look exactly like a shop emptying its shelves, there are some guards. A scrape that returns nothing is treated as a failure, changes nothing in the database, and makes the run exit with code 2. A scrape that returns less than half of what that shop usually has (`STOCKIST_HEALTH_RATIO`) doesn't trigger any delistings. If it's low twice in a row (`CONSECUTIVE_UNHEALTHY_THRESHOLD`) the lower number becomes the new normal and delistings resume.

## Delivery

Alerts aren't sent straight away. When a change is detected it's written to a `notification_outbox` table in the same database transaction as the change itself, so a crash can't leave you with a recorded change and no alert. At the end of each shop's scrape the pending alerts for that shop are sent.

If a send fails with a timeout, a 5xx or a 429 it's tried again on later runs, and given up on after `OUTBOX_MAX_AGE_HOURS` (24) or `OUTBOX_MAX_ATTEMPTS` (5), whichever comes first. Other failures, such as a deleted webhook, aren't retried. Each alert is only sent once per messenger, so a retry won't duplicate it for a messenger that already got it.

Sends are spaced `MESSAGE_SEND_DELAY` seconds apart (0.5). If Discord answers 429, that messenger is paused for the rest of the run and its remaining alerts wait for the next one.

## Cooldown

To stop an item that's flapping from spamming you, a repeat alert of the same kind for the same item is suppressed for `NOTIFICATION_COOLDOWN_MINUTES` (60) after the last one was sent. The exception is "In stock" alerts, which are never suppressed. The change itself is still recorded, so the next alert compares against the up-to-date state.

## Tuning

The thresholds above are constants in `constants.py`. There's no config option for them, so edit the file and they apply from the next run. `REQUEST_TIMEOUT` (5 seconds) is there too, and is the one to raise if a slow shop keeps coming back empty.
