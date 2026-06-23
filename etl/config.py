import os

BASE_URL = "https://otel-hackathon-data-site.vercel.app"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon",
)
REQUEST_DELAY_MS = 400
DETAIL_MAX_RETRIES = 3
NAVIGATION_TIMEOUT_MS = 30_000
ELEMENT_TIMEOUT_MS = 15_000
MAX_LIST_PAGES = 20

OUTPUT_RESERVATIONS = "data/raw_reservations.json"
OUTPUT_LOOKUPS = "data/raw_lookups.json"
OUTPUT_VERIFY = "data/raw_verify.json"
OUTPUT_VERIFY_TARGETS = "data/verify_targets.json"
OUTPUT_VERIFY_RAW_TEXT = "data/verify.raw_text"
VERIFY_URL = f"{BASE_URL}/verify"

# Verification targets aligned to anchor date 2026-06-11 (see data/verify_targets.json).
#
# Do not confuse these metrics:
#   - total_reservations (250)  = distinct bookings
#   - total_stay_rows (516)     = fact-table rows at grain reservation × stay_date
#   - otb_room_nights (649)     = SUM(number_of_spaces) for Reserved, stay_date ≥ anchor
#                                 — NOT the same as total_stay_rows; validated at load, not extract
#   - 455 (brief §15)           = stale static figure in what_do_i_want_to_do.md — ignore
EXPECTED_ANCHOR_DATE = "2026-06-11"
EXPECTED = {
    "total_reservations": 250,  # distinct reservation_id
    "total_stay_rows": 516,  # Σ stay_rows in raw extract; must match verify total_stay_rows
    "room_type_lookup": 3,
    "market_code_lookup": 10,
    "channel_code_lookup": 4,
}
# Post-load only (not checked by etl.extract):
VERIFY_OTB_ROOM_NIGHTS = 649

LOOKUP_SORT_KEYS = {
    "room_type_lookup": "space_type",
    "market_code_lookup": "market_code",
    "channel_code_lookup": "channel_code",
}
