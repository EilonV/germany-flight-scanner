"""Telegram alerting with de-duplication.

You asked not to be pinged on every scan - only when the price actually hits.
So every alert-worthy event is recorded in data/state.json and never fires
twice for the same fare at the same or a higher price.
"""
import datetime as dt
import json
import os
import urllib.parse
import urllib.request

import config

API = "https://api.telegram.org/bot{token}/sendMessage"


# --------------------------------------------------------------------------- state
def load_state(path=None):
    path = path or config.STATE_FILE
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    state.setdefault("alerted", {})
    state.setdefault("all_time_low", None)
    state.setdefault("history", [])
    return state


def save_state(state, path=None):
    path = path or config.STATE_FILE
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)


def record_history(state, offers):
    """Append one point per scan so the page can draw a price trend."""
    if not offers:
        return
    state["history"].append(
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "min_price": min(o.price for o in offers),
            "count": len(offers),
        }
    )
    state["history"] = state["history"][-400:]


# --------------------------------------------------------------------------- decide
def alerts_for(offers, state):
    """Which offers deserve a message right now.

    Fires when:
      * a fare is under PRICE_THRESHOLD_NIS and we have not already alerted it
        at that price or cheaper, or
      * ALERT_ON_NEW_LOW and the fare beats the best price ever recorded.
    """
    out = []
    if not offers:
        return out

    low = state.get("all_time_low")
    cheapest = min(offers, key=lambda o: o.price)

    for offer in offers:
        previously = state["alerted"].get(offer.key)
        under_threshold = offer.price < config.PRICE_THRESHOLD_NIS
        is_new_low = (
            config.ALERT_ON_NEW_LOW
            and offer is cheapest
            and (low is None or offer.price < low)
        )
        already = previously is not None and offer.price >= previously

        if (under_threshold or is_new_low) and not already:
            out.append((offer, "threshold" if under_threshold else "new low"))
    return out


def commit_alerts(alerts, offers, state):
    for offer, _ in alerts:
        state["alerted"][offer.key] = offer.price
    if offers:
        cheapest = min(o.price for o in offers)
        if state.get("all_time_low") is None or cheapest < state["all_time_low"]:
            state["all_time_low"] = cheapest


# --------------------------------------------------------------------------- send
def _escape(text):
    for a, b in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")):
        text = text.replace(a, b)
    return text


def format_message(offer, reason):
    bags = []
    for icon, bag in (("backpack", offer.backpack), ("cabin bag", offer.cabin),
                      ("checked bag", offer.checked)):
        bags.append(f"{icon}: {'yes' if bag.included else 'no'}")

    hub = offer.layover_summary
    airlines = ", ".join(offer.airlines) or "unknown airline"
    tag = f" (Flight + {offer.ground_mode})" if offer.ground_mode else ""
    headline = (
        "Cheap flight found!" if reason == "threshold" else "New lowest price!"
    )
    return (
        f"<b>{_escape(headline)}</b>\n"
        f"<b>{offer.price:,} NIS</b> round trip{_escape(tag)}\n\n"
        f"{_escape(config.ORIGIN)} to {_escape(config.DESTINATION)} "
        f"via {_escape(hub)}\n"
        f"Out {_escape(offer.outbound_date)} at {_escape(offer.depart_time)}, "
        f"back {_escape(offer.return_date)}\n"
        f"{_escape(airlines)} - {_escape(offer.duration)}, {offer.stops} stop\n"
        f"{_escape(' | '.join(bags))}\n\n"
        f'<a href="{_escape(offer.booking_url)}">Open in Google Flights</a>'
    )


def send(text, token=None, chat_id=None):
    token = token or config.TELEGRAM_BOT_TOKEN
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("  [telegram] not configured - set TELEGRAM_BOT_TOKEN and "
              "TELEGRAM_CHAT_ID in .env or Actions secrets")
        return False

    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()
    try:
        with urllib.request.urlopen(
            API.format(token=token), data=payload, timeout=20
        ) as resp:
            ok = json.load(resp).get("ok", False)
            print(f"  [telegram] sent: {ok}")
            return ok
    except Exception as exc:  # noqa: BLE001 - never let a failed ping kill the scan
        print(f"  [telegram] FAILED: {type(exc).__name__}: {exc}")
        return False


def send_error(summary):
    """Loud failure. A broken scraper must not look like an expensive market."""
    return send(
        "<b>Flight scanner problem</b>\n"
        f"{_escape(summary)}\n\n"
        "No results were produced this run. This usually means Google changed "
        "the page and the parser needs updating."
    )
