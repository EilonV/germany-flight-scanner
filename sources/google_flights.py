"""Google Flights source.

Why Playwright and not a plain HTTP GET:
Google server-renders results into a `script.ds:1` payload for popular routes,
which is what fast-flights parses. For TLV->NUE that payload is empty at every
stop count and every date - the itineraries arrive later over XHR and are only
ever written into the DOM. Verified during build: TLV->FRA and FRA->NUE both
return data over plain HTTP, but TLV->NUE returns nothing, while a rendered
page returns 18 itineraries. So we render, then read the DOM.

We parse accessibility labels rather than Google's obfuscated CSS classes.
Each result card carries one master aria-label containing everything:

  "From 2677 Israeli new shekels round trip total. 1 stop flight with
   Lufthansa. Leaves Ben Gurion Airport at 8:00 AM on Tuesday, June 1 and
   arrives at Nuremberg Airport at 2:05 PM on Tuesday, June 1. Total duration
   7 hr 5 min.  Layover (1 of 1) is a 1 hr 40 min layover at Frankfurt Airport
   in Frankfurt am Main. Select flight"

Those strings are driven by screen-reader requirements and change far less
often than class names like .pIav2d.
"""
import re
import time

import airportsdata
from fast_flights import FlightQuery, Passengers, create_query

import config
from models import Baggage, Layover, Offer

_IATA = airportsdata.load("IATA")
_NBSP = " "

CARD_SELECTOR = "li.pIav2d"
MASTER_LABEL_RE = re.compile(r"Leaves .+? and arrives at ", re.S)
LAYOVER_RE = re.compile(r"Layover \(\d+ of \d+\) is an? (.+?) layover at (.+?) in ")
ROUTE_RE = re.compile(
    r"Leaves (.+?) at (.+?) on (.+?) and arrives at (.+?) at (.+?) on ([^.]+)\."
)


def _clean(s):
    return re.sub(r"\s+", " ", (s or "").replace(_NBSP, " ")).strip()


def _dur_to_minutes(text):
    h = re.search(r"(\d+)\s*hr", text)
    m = re.search(r"(\d+)\s*min", text)
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def _country_of(code, name):
    rec = _IATA.get(code.upper()) if code else None
    if rec:
        return rec.get("country", "")
    if name:
        want = name.lower().replace(" airport", "").strip()
        for r in _IATA.values():
            if want and want in r.get("name", "").lower():
                return r.get("country", "")
    return ""


GROUND_PATTERNS = (
    ("Bus", ("Flight + Bus", "Bus Services", "Bus Service")),
    ("Train", ("Flight + Train", "Rail Services", "Express Rail", "Deutsche Bahn",
               "Flight + Rail")),
)


def _ground_mode(body):
    """Return "Bus"/"Train" if this itinerary contains a surface leg, else "".

    Lufthansa through-tickets TLV->MUC/FRA plus a coach or ICE to Nuremberg.
    Google badges those "Flight + Bus" / "Flight + Train".
    """
    for mode, needles in GROUND_PATTERNS:
        if any(n in body for n in needles):
            return mode
    return ""


def build_query(outbound_date, return_date, carry_on_bags=0, checked_bags=0):
    """One round-trip query with all hard filters pushed server-side."""
    return create_query(
        flights=[
            FlightQuery(
                date=outbound_date,
                from_airport=config.ORIGIN,
                to_airport=config.DESTINATION,
                max_stops=config.MAX_STOPS,
                max_layover_minutes=config.MAX_LAYOVER_MINUTES,
                # None = every time of day; otherwise must land by this hour.
                latest_arrival_hour=config.LATEST_ARRIVAL_HOUR,
            ),
            FlightQuery(
                date=return_date,
                from_airport=config.DESTINATION,
                to_airport=config.ORIGIN,
                max_stops=config.MAX_STOPS,
                max_layover_minutes=config.MAX_LAYOVER_MINUTES,
            ),
        ],
        trip="round-trip",
        seat=config.SEAT,
        currency=config.CURRENCY,
        language=config.LANGUAGE,
        passengers=Passengers(adults=config.ADULTS),
        carry_on_bags=carry_on_bags,
        checked_bags=checked_bags,
    )


def _parse_card(card, outbound_date, return_date, url):
    labels = [
        _clean(n.get_attribute("aria-label"))
        for n in card.query_selector_all("[aria-label]")
    ]
    master = next((l for l in labels if MASTER_LABEL_RE.search(l)), None)
    if not master:
        return None

    m_price = re.search(r"(\d[\d,]*) Israeli new shekels", master)
    m_route = ROUTE_RE.search(master)
    if not (m_price and m_route):
        return None

    m_dur = re.search(r"Total duration ([^.]+)\.", master)
    duration = _clean(m_dur.group(1)) if m_dur else ""

    if re.search(r"\bNonstop\b", master, re.I):
        stops = 0
    else:
        m_stop = re.search(r"(\d+) stop", master)
        stops = int(m_stop.group(1)) if m_stop else 0

    m_air = re.search(r"flight with ([^.]+?)\.", master)
    airlines = []
    if m_air:
        airlines = [
            a.strip()
            for a in re.split(r",| and ", m_air.group(1))
            if a.strip() and not a.strip().lower().startswith("operated by")
        ]

    # Layovers: duration + airport name from the aria-label, IATA code from the
    # nested span inside that same node.
    layovers = []
    for node in card.query_selector_all("[aria-label]"):
        m = LAYOVER_RE.match(_clean(node.get_attribute("aria-label")))
        if not m:
            continue
        code = ""
        for sp in node.query_selector_all("span"):
            t = _clean(sp.inner_text())
            if re.fullmatch(r"[A-Z]{3}", t):
                code = t
                break
        name = m.group(2)
        layovers.append(
            Layover(
                airport_code=code,
                airport_name=name,
                country=_country_of(code, name),
                minutes=_dur_to_minutes(m.group(1)),
            )
        )

    body = _clean(card.inner_text())
    ground = _ground_mode(body)
    return Offer(
        price=int(m_price.group(1).replace(",", "")),
        outbound_date=outbound_date,
        return_date=return_date,
        depart_time=_clean(m_route.group(2)),
        arrive_time=_clean(m_route.group(5)),
        depart_airport=_clean(m_route.group(1)),
        arrive_airport=_clean(m_route.group(4)),
        duration=duration,
        duration_minutes=_dur_to_minutes(duration),
        stops=stops,
        airlines=airlines,
        layovers=layovers,
        ground_mode=ground,
        booking_url=url,
    )


def scrape_combo(page, outbound_date, return_date, carry_on_bags=0, checked_bags=0):
    """Scrape one date pair. Retries, because a combo sometimes renders empty."""
    query = build_query(outbound_date, return_date, carry_on_bags, checked_bags)
    url = query.url()

    for attempt in range(1, config.RETRIES + 1):
        page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_TIMEOUT_MS)
        try:
            page.wait_for_selector(CARD_SELECTOR, timeout=config.RESULTS_TIMEOUT_MS)
        except Exception:
            if attempt == config.RETRIES:
                return []
            time.sleep(2 * attempt)
            continue
        page.wait_for_timeout(config.SETTLE_MS)

        offers, seen = [], set()
        for card in page.query_selector_all(CARD_SELECTOR):
            offer = _parse_card(card, outbound_date, return_date, url)
            if offer and offer.key not in seen:
                seen.add(offer.key)
                offers.append(offer)
        if offers:
            return offers
        if attempt < config.RETRIES:
            time.sleep(2 * attempt)
    return []


def attach_baggage(offers, bag_inclusive):
    """Fill in the three bag icons.

    `bag_inclusive` maps bag type -> {offer.key: cheapest total including it}.

    Note we do NOT report an "add-on fee". Asking Google for a checked bag
    returns a *cheaper* headline price on this route (1831 vs 1848 NIS),
    because it re-ranks to a different fare brand rather than adding a fee to
    the same fare. So a subtraction would be meaningless. What we report
    instead is real: the cheapest round-trip total that includes each bag.
    """
    for o in offers:
        o.backpack = Baggage(
            included=True,
            total_with_bag=o.price,
            note=(
                "Personal item / small backpack is included in every economy "
                "fare on this route."
            ),
            source="policy",
        )

        for attr, label in (("cabin", "carry_on"), ("checked", "checked")):
            total = bag_inclusive.get(label, {}).get(o.key)
            if total is None:
                setattr(
                    o,
                    attr,
                    Baggage(
                        included=False,
                        total_with_bag=None,
                        note="Google returned no fare including this bag for this itinerary.",
                        source="measured",
                    ),
                )
            elif total <= o.price:
                extra = (
                    f" ({o.price - total:,} NIS less than the headline fare)."
                    if total < o.price
                    else " - same as the headline fare."
                )
                setattr(
                    o,
                    attr,
                    Baggage(
                        included=True,
                        total_with_bag=total,
                        note=f"Included. Cheapest fare with this bag: {total:,} NIS" + extra,
                        source="measured",
                    ),
                )
            else:
                setattr(
                    o,
                    attr,
                    Baggage(
                        included=False,
                        total_with_bag=total,
                        note=(
                            f"Not in the headline fare. Cheapest fare including it: "
                            f"{total:,} NIS (+{total - o.price:,} NIS)."
                        ),
                        source="measured",
                    ),
                )
