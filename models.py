"""Normalized data model. The scraper produces Offers; everything else consumes them."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Layover:
    airport_code: str        # "FRA" ("" if Google only gave us a name)
    airport_name: str        # "Frankfurt Airport"
    country: str             # ISO-2, resolved via airportsdata ("" if unknown)
    minutes: int


@dataclass
class Baggage:
    """What a bag type costs, measured rather than estimated.

    Google re-prices to a different fare brand when you ask for a bag, so an
    "add-on fee" is not something we can honestly derive. Instead we record the
    cheapest round-trip total that *includes* each bag type.
    """
    included: bool = False
    total_with_bag: Optional[int] = None   # NIS, cheapest fare including this bag
    note: str = ""                         # shown in the tooltip
    source: str = "policy"                 # "measured" | "policy"


@dataclass
class Offer:
    price: int                     # round-trip total, NIS
    outbound_date: str
    return_date: str
    depart_time: str               # "7:00 AM" (local, TLV)
    arrive_time: str               # local, NUE
    depart_airport: str
    arrive_airport: str
    duration: str                  # "7 hr 45 min"
    duration_minutes: int
    stops: int
    airlines: list[str] = field(default_factory=list)
    layovers: list[Layover] = field(default_factory=list)
    ground_mode: str = ""          # "Bus" / "Train" / "" if pure flight
    backpack: Baggage = field(default_factory=Baggage)
    cabin: Baggage = field(default_factory=Baggage)
    checked: Baggage = field(default_factory=Baggage)
    booking_url: str = ""

    @property
    def key(self) -> str:
        """Stable identity for de-duplication and alert state."""
        hubs = "-".join(l.airport_code or l.airport_name for l in self.layovers)
        return f"{self.outbound_date}|{self.return_date}|{self.depart_time}|{hubs}"

    @property
    def layover_summary(self) -> str:
        if not self.layovers:
            return "nonstop"
        return ", ".join(
            f"{_hm(l.minutes)} {l.airport_code or l.airport_name}" for l in self.layovers
        )

    @property
    def max_layover_minutes(self) -> int:
        return max((l.minutes for l in self.layovers), default=0)

    def to_dict(self) -> dict:
        return asdict(self)


def _hm(minutes: int) -> str:
    h, m = divmod(max(minutes, 0), 60)
    if h and m:
        return f"{h} hr {m} min"
    if h:
        return f"{h} hr"
    return f"{m} min"
