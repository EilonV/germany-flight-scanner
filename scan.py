"""Entry point: search -> filter -> render -> notify.

  python scan.py                 full scan, writes state, sends Telegram
  python scan.py --dry-run       scan and render, but touch nothing and send nothing
  python scan.py --no-bags       skip the two extra bag passes (3x faster)
  python scan.py --test-telegram send one test message and exit
"""
import itertools
import sys
import traceback

from playwright.sync_api import sync_playwright

import config
import filters
import notify
import render
from sources import google_flights as gf


def _combos():
    return list(itertools.product(config.OUTBOUND_DATES, config.RETURN_DATES))


def collect(page, carry_on_bags=0, checked_bags=0, label=""):
    """Scrape every date combination for one baggage configuration."""
    found = []
    for outbound, ret in _combos():
        offers = gf.scrape_combo(page, outbound, ret, carry_on_bags, checked_bags)
        print(f"  {label}{outbound} -> {ret}: {len(offers)} raw", flush=True)
        found.extend(offers)
    return found


def run(dry_run=False, with_bags=True):
    print(f"Scanning {config.ORIGIN} -> {config.DESTINATION}, "
          f"{len(_combos())} date combinations\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(locale="en-US")
        try:
            base = collect(page, label="base     ")

            bag_inclusive = {"carry_on": {}, "checked": {}}
            if with_bags:
                print()
                for label, kwargs in (
                    ("carry_on", {"carry_on_bags": 1}),
                    ("checked", {"checked_bags": 1}),
                ):
                    for offer in collect(page, label=f"{label:<9}", **kwargs):
                        cur = bag_inclusive[label].get(offer.key)
                        if cur is None or offer.price < cur:
                            bag_inclusive[label][offer.key] = offer.price
        finally:
            browser.close()

    if not base:
        msg = ("Google Flights returned no parseable results for any date "
               "combination. The page layout has probably changed.")
        print(f"\n!! {msg}")
        if not dry_run:
            notify.send_error(msg)
        return 1

    offers = filters.dedupe(base)
    offers, rejected = filters.apply(offers)
    gf.attach_baggage(offers, bag_inclusive)
    offers = filters.sort_offers(offers)

    print(f"\n{len(offers)} offers passed filters"
          + (f" | rejected: {rejected}" if rejected else ""))
    print(f"{'price':>8}  {'dates':<13} {'dep':<9} {'via':<22} {'duration':<12} airline")
    for o in offers:
        tag = f" [Flight+{o.ground_mode}]" if o.ground_mode else ""
        print(f"{o.price:>8,}  {o.outbound_date[5:]}->{o.return_date[5:]}  "
              f"{o.depart_time:<9} {o.layover_summary:<22} {o.duration:<12} "
              f"{', '.join(o.airlines)}{tag}")

    state = notify.load_state()
    alerts = notify.alerts_for(offers, state)

    if dry_run:
        print(f"\n[dry-run] would send {len(alerts)} Telegram message(s); "
              "no state written")
        render.render(offers, state, rejected, path="index.preview.html")
        print("[dry-run] wrote index.preview.html")
        return 0

    for offer, reason in alerts:
        notify.send(notify.format_message(offer, reason))
    notify.commit_alerts(alerts, offers, state)
    notify.record_history(state, offers)
    notify.save_state(state)
    out = render.render(offers, state, rejected)
    print(f"\nSent {len(alerts)} alert(s). Wrote {out} and {config.STATE_FILE}.")
    return 0


def main():
    args = set(sys.argv[1:])

    if "--test-telegram" in args:
        ok = notify.send(
            "<b>Flight scanner test</b>\nTelegram is wired up correctly. "
            "You will get a message here when a fare hits your target."
        )
        return 0 if ok else 1

    try:
        return run(dry_run="--dry-run" in args, with_bags="--no-bags" not in args)
    except Exception:
        traceback.print_exc()
        if "--dry-run" not in args:
            notify.send_error(
                "The scanner crashed. See the GitHub Actions log for the traceback."
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
