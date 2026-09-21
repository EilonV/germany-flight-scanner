"""Scanner configuration. Everything you might want to tweak lives here."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

ORIGIN = "TLV"
DESTINATION = "NUE"

# Flexible dates: every outbound is paired with every return.
OUTBOUND_DATES = ["2027-06-01", "2027-06-02"]
RETURN_DATES = ["2027-06-07", "2027-06-08"]

CURRENCY = "ILS"
LANGUAGE = "en-US"
ADULTS = 1
SEAT = "economy"

# --- Hard filters (applied server-side by Google where possible) ---
MAX_STOPS = 1
MAX_LAYOVER_MINUTES = 300          # "5 hours or less"

# Arrival cutoff in Germany, or None to scan every time of day.
# Measured cost of a 20:00 cutoff on this route: about 437 NIS, because the
# cheapest Frankfurt connections land after 20:00. Set to an hour (e.g. 20)
# to reinstate it.
LATEST_ARRIVAL_HOUR = None

# Ground legs. Google sells some Lufthansa itineraries as "Flight + Bus" or
# "Flight + Train" (a coach or ICE from MUC/FRA to Nuremberg on one ticket).
# These are the cheapest options on this route by a wide margin, but you asked
# for flights only, so they are excluded.
INCLUDE_GROUND_LEGS = False

# --- Connection country blocklist (ISO 3166-1 alpha-2) ---
# Your explicit choices first, then countries an Israeli passport cannot transit anyway.
BLOCKED_COUNTRIES = {
    "TR",  # Turkey   (blocks Istanbul / Turkish Airlines)
    "JO",  # Jordan   (Amman / Royal Jordanian)
    "EG",  # Egypt    (Cairo / EgyptAir)
    "LB", "SY", "IQ", "IR", "SA", "YE", "LY", "SD",
}

# --- Alerting ---
PRICE_THRESHOLD_NIS = int(os.getenv("PRICE_THRESHOLD_NIS", "800"))
ALERT_ON_NEW_LOW = os.getenv("ALERT_ON_NEW_LOW", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# --- Scraper behaviour ---
PAGE_TIMEOUT_MS = 60000
RESULTS_TIMEOUT_MS = 45000
SETTLE_MS = 3500
RETRIES = 3          # a combo occasionally renders empty; retry before believing it
STATE_FILE = "data/state.json"
OUTPUT_HTML = "index.html"
