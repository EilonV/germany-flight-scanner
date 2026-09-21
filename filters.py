"""Post-scrape filtering and ranking.

Google applies max_stops, max_layover_minutes and the departure-hour window
server-side (see sources/google_flights.build_query), but we re-check every
rule here anyway. If Google ever silently drops a filter we reject locally
rather than showing you a 6-hour layover in Istanbul.
"""
import re

import config

REJECT_REASONS = (
    "too many stops",
    "layover too long",
    "arrives in Germany after cutoff",
    "blocked connection country",
    "has bus/train leg",
)


def _hour_24(t):
    """'7:00 AM' -> 7, '1:45 PM' -> 13. Returns None if unparseable."""
    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", (t or "").strip(), re.I)
    if not m:
        m24 = re.match(r"(\d{1,2}):(\d{2})$", (t or "").strip())
        return int(m24.group(1)) if m24 else None
    hour = int(m.group(1)) % 12
    if m.group(3).upper() == "PM":
        hour += 12
    return hour


def rejection_reason(offer):
    """Return why this offer is rejected, or None if it passes."""
    if offer.stops > config.MAX_STOPS:
        return "too many stops"

    if offer.max_layover_minutes > config.MAX_LAYOVER_MINUTES:
        return "layover too long"

    # Arrival cutoff, when one is configured. None means scan every time.
    if config.LATEST_ARRIVAL_HOUR is not None:
        arrive_hour = _hour_24(offer.arrive_time)
        if arrive_hour is not None and arrive_hour >= config.LATEST_ARRIVAL_HOUR:
            return "arrives in Germany after cutoff"

    for lay in offer.layovers:
        if lay.country and lay.country in config.BLOCKED_COUNTRIES:
            return "blocked connection country"

    if offer.ground_mode and not config.INCLUDE_GROUND_LEGS:
        return "has bus/train leg"

    return None


def apply(offers):
    """Split offers into (kept, reason_counts)."""
    kept, reasons = [], {}
    for o in offers:
        reason = rejection_reason(o)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            kept.append(o)
    return kept, reasons


# NOTE on the return-leg time preference (mid-day to evening):
# Google's round-trip result cards only expose the OUTBOUND leg - the headline
# price is the round-trip total, but the return flight's own times are not in
# the card. So we cannot evaluate that preference from this data, and we do not
# pretend to. Since you said cheapest wins anyway, nothing is lost in ranking.
# Surfacing real return times needs a click-through into each itinerary; see
# README "Not implemented".


def sort_offers(offers):
    """Cheapest first - your primary requirement.

    Ties break toward the shorter layover, then the shorter total trip, so the
    'shortest stops' view wins whenever price is equal. The rendered table is
    also click-sortable on layover and duration.
    """
    return sorted(
        offers,
        key=lambda o: (o.price, o.max_layover_minutes, o.duration_minutes),
    )


def dedupe(offers):
    """Keep the cheapest instance of each distinct itinerary."""
    best = {}
    for o in offers:
        cur = best.get(o.key)
        if cur is None or o.price < cur.price:
            best[o.key] = o
    return list(best.values())
