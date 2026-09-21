# TLV → Nuremberg flight scanner

Scans Google Flights twice a day for **Tel Aviv → Nuremberg, June 2027**, filters to
the itineraries you actually want, publishes a sortable price table as a website,
and pings Telegram when a fare hits your target.

## What it enforces

| Rule | Value |
|---|---|
| Stops | max 1 |
| Layover | ≤ 5 hours |
| Times | unrestricted — every departure and arrival time is scanned |
| Ground legs | excluded — flights only, no bus or train legs |
| Blocked connections | Turkey, Jordan, Egypt (+ LB, SY, IQ, IR, SA, YE, LY, SD) |
| Dates | out 1 or 2 June, back 7 or 8 June (4 combinations) |
| Currency | NIS, round-trip total, 1 adult, economy |
| Sort | cheapest first; layover and duration are click-sortable |

All prices are **round-trip totals** for 1 adult, not one-way fares.

### Not implemented: return-leg timing

Google's round-trip result cards expose only the **outbound** leg — the price is
the round-trip total, but the return flight's own times are not in the card. So
the 20:00 arrival cutoff is enforced on the outbound leg only, and no preference
is applied to the return. Surfacing real return times means clicking into each
itinerary with Playwright; say the word and I will add it.

## Two things worth knowing before you use it

**1. There is no nonstop TLV → Nuremberg flight.** The route does not exist — no
airline flies it. Nuremberg's only usable nonstop links are Frankfurt (Lufthansa),
Amsterdam (KLM), Paris CDG (Air France) and Istanbul (Turkish, which you blocked).
So every result here has exactly one stop.

**2. Nothing on this route is anywhere near ₪800 round trip.** With ground legs
excluded, the measured floor is about **₪2,150** — the 04:45 Lufthansa via
Frankfurt. That is roughly 2.7x the ₪800 target, so the threshold will never fire
on its own. This is why `ALERT_ON_NEW_LOW=true` is on by default: you still get
told whenever the price beats its own record.

Allowing the Lufthansa `Flight + Bus` fares back in (`INCLUDE_GROUND_LEGS = True`)
drops the floor to about ₪1,830 — those are a single Lufthansa ticket with a
through-booked coach from Munich, not a separate booking.

Note also that the 04:45 departure is only visible because departure time is
unconstrained. An 05:00 earliest-departure rule hid it and cost about ₪500.

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env      # then fill it in
```

### Telegram

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the **token**.
2. Send your new bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy
   `result[0].message.chat.id` — that is your **chat ID**.
3. Put both in `.env`:

   ```
   TELEGRAM_BOT_TOKEN=8123456789:AAE...
   TELEGRAM_CHAT_ID=123456789
   PRICE_THRESHOLD_NIS=800
   ```

4. Verify: `python scan.py --test-telegram`

For the hosted runs, add the same two names under
**Settings → Secrets and variables → Actions → New repository secret**.
The token never goes in the repo. `PRICE_THRESHOLD_NIS` and `ALERT_ON_NEW_LOW`
can be set as repository *variables* if you want to change them without editing code.

## Running

```bash
python scan.py              # full scan: writes index.html, state, sends alerts
python scan.py --dry-run    # scan + render to index.preview.html, no state, no alerts
python scan.py --no-bags    # skip the two baggage passes, ~3x faster
python scan.py --test-telegram
```

## Hosting (free, no restarts)

`.github/workflows/scan.yml` runs at 05:00 and 17:00 UTC (08:00 / 20:00 Israel) and
commits `index.html` + `data/state.json` back to the repo. Enable
**Settings → Pages → Deploy from branch → main / root** and the table is served at
`https://<user>.github.io/<repo>/`.

Those per-run commits double as the fix for GitHub auto-disabling scheduled
workflows after 60 days of inactivity, so no keepalive hack is needed.

> GitHub Pages on a free account requires a **public** repo. Only flight data and
> code live here; the Telegram token stays in Actions secrets. If you would rather
> keep it private, drop the Pages step and have the workflow send the HTML to you
> as a build artifact instead.

## How it works

`scan.py` → `sources/google_flights.py` (Playwright) → `filters.py` →
`render.py` (website) → `notify.py` (Telegram).

**Why Playwright and not plain HTTP.** `fast-flights` parses the `script.ds:1`
payload Google server-renders. For TLV→NUE that payload is empty at every stop
count and every date — verified: `TLV→FRA` and `FRA→NUE` both return data over
plain HTTP, but `TLV→NUE` returns nothing, while a rendered page returns 18
itineraries. The results arrive over XHR and only ever land in the DOM.

**Why aria-labels and not CSS classes.** Each result card carries one master
accessibility label with price, stops, airline, times, duration and layover in it.
Those strings are driven by screen-reader requirements and are far more stable than
obfuscated class names like `.pIav2d`.

**Baggage.** Asking Google for a checked bag returns a *cheaper* headline price on
this route, because it re-ranks to a different fare brand instead of adding a fee to
the same fare. So an "add-on fee" cannot be honestly derived by subtraction. Each
icon instead reports the cheapest round-trip total that *includes* that bag —
measured, not estimated. Hover any icon to see it.

`fast-flights` 3.1.0 imports `typing_extensions` without declaring it, so
`requirements.txt` pins it explicitly.

## Tuning

Everything is in `config.py`: dates, hour windows, layover cap, the country
blocklist, and `INCLUDE_FLIGHT_PLUS_BUS` if you want to hide the coach-leg fares.
