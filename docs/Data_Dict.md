# Data Dictionary — Revenue Manager Agent

A complete reference for every column across all four tables (plus the small
`dataset_metadata` table added by the ETL), with the **full form / expansion**
and a **plain-English meaning**. All code values (OTA, SMERF, CNI, …) are
expanded at the end.

> **Anchor date:** `2026-06-11` (stored in `dataset_metadata.as_of_date`) — the
> dataset's frozen "today" that grounds every window.

---

## Table 1: `reservations_hackathon` — the fact table

**Grain:** one row per `reservation_id` × `stay_date` (one row per booking, per night).
A 3-night booking = 3 rows; `number_of_spaces` says how many rooms per night.

| Column | Full form / how to read it | Meaning |
|---|---|---|
| `reservation_stay_id` | Reservation-Stay ID | Auto-generated unique ID for **this single row** (one booking-night). Primary key. Counts rows, never bookings. |
| `reservation_id` | Reservation ID | The actual **booking** identifier (e.g. `R0001`). Repeats across the booking's nights. Bookings = `COUNT(DISTINCT reservation_id)`. |
| `arrival_date` | Arrival date | The day the guest **checks in**. |
| `departure_date` | Departure date | The day the guest **checks out**. Guest stays *up to but not including* this date. |
| `stay_date` | Stay date | The **specific night** this row represents. Key date for "revenue on the books." |
| `reservation_status` | Reservation status | `Reserved` (active) or `Cancelled`. Column is `reservation_status`, **not** `status`. |
| `create_datetime` | Creation date-time | **When the booking was made** (timestamp). Used for booking pace / "what changed." |
| `cancellation_datetime` | Cancellation date-time | **When it was cancelled** (timestamp). Null unless cancelled. |
| `guest_country` | Guest country | Guest's country code (e.g. `DE`, `GB`). Optional. |
| `is_block` | Is block (boolean) | `true` if a **group/block** booking (conference, event, choir); `false` for individuals. |
| `is_walk_in` | Is walk-in (boolean) | `true` if the guest **walked in** without a prior booking. |
| `number_of_spaces` | Number of spaces (= number of rooms) | How many **rooms** this reservation holds for that night. "Spaces" = rooms. Room nights = `SUM(number_of_spaces)`. |
| `space_type` | Space type (= room type code) | The **room type code** (`EX`, `KS`, `TB`). Joins to `room_type_lookup`. |
| `market_code` | Market (segment) code | The **business segment** (e.g. `OTA`, `CSR`). *Who the business is priced as.* Joins to `market_code_lookup`. |
| `channel_code` | Channel code | The **booking path** (e.g. `WEB`, `REC`). *How the booking came in.* Joins to `channel_code_lookup`. |
| `source_name` | Source name | Human-readable booking source (e.g. `Booking.com`, `Expedia`, `Brand website`). Free text. |
| `rate_plan_code` | Rate plan code | The **pricing plan** code (e.g. `GROUPBB`, `EXPBARB`). |
| `daily_room_revenue_before_tax` | Daily room revenue (before tax) | **Room-only** money for that night, all rooms, before tax. = `adr_room × number_of_spaces`. |
| `daily_total_revenue_before_tax` | Daily total revenue (before tax) | **Total** money for that night (rooms **+** packages/breakfast), before tax. ≥ room revenue. |
| `nights` | Nights (length of stay) | Total nights of the whole reservation. Repeated on every night-row (don't sum it). |
| `adr_room` | ADR — Average Daily Rate (room) | The typical **price per room** for the reservation. Repeated on every night-row. |
| `lead_time` | Lead time | Days between booking creation and arrival (`arrival_date − create_datetime`). |
| `company_name` | Company name | Company tied to the booking (corporate/group). Optional. |
| `travel_agent_name` | Travel agent name | The travel agent, if any. Optional. |

---

## Table 2: `room_type_lookup` — 3 rows, one per room type

| Column | Full form | Meaning |
|---|---|---|
| `space_type` | Space type (room type code) | Primary key. The code (`EX`, `KS`, `TB`) the fact table joins to. |
| `room_class` | Room class | Broad class: `Standard` or `Executive`. |
| `display_name` | Display name | Human-friendly name (e.g. "Executive King"). |
| `number_of_rooms` | Number of rooms | Physical rooms of this type in the hotel. Sums to **98** = total capacity. |

---

## Table 3: `market_code_lookup` — 10 rows, one per segment

| Column | Full form | Meaning |
|---|---|---|
| `market_code` | Market (segment) code | Primary key. The segment code the fact table joins to. |
| `market_name` | Market name | Human-friendly segment name. |
| `macro_group` | Macro group | Broader grouping: `Retail`, `Corporate`, `MICE`, `Leisure`, `Leisure Group`. |
| `description` | Description | Plain-English description of the segment. |

---

## Table 4: `channel_code_lookup` — 4 rows, one per channel

| Column | Full form | Meaning |
|---|---|---|
| `channel_code` | Channel code | Primary key. The channel code the fact table joins to. |
| `channel_name` | Channel name | Human-friendly channel name. |
| `channel_group` | Channel group | Broad grouping: `Digital`, `Direct`, `Offline`. |

---

## Table 5: `dataset_metadata` — 1 row, added by the ETL

| Column | Full form | Meaning |
|---|---|---|
| `id` | ID | Always `1` (only one row allowed). |
| `as_of_date` | "As-of" date | The anchor "today" for the dataset (`2026-06-11`). Grounds all windows. |
| `loaded_at` | Loaded-at timestamp | When the ETL last loaded the data. |

---

## Code values expanded (these full forms matter most)

### Room types (`space_type`)

| Code | Full form | Class |
|---|---|---|
| `EX` | Executive King | Executive |
| `KS` | Standard King | Standard |
| `TB` | Standard Twin | Standard |

### Market / segment codes (`market_code`) — grouped by macro-group

| Code | Full form | Macro group |
|---|---|---|
| `BAR` | Best Available Retail | Retail |
| `PROM` | Promotional Retail | Retail |
| `OTA` | Online Travel Agency (Booking.com, Expedia) | Retail |
| `FIT` | Free Independent Traveller | Leisure |
| `CSR` | Corporate Negotiated | **Corporate** |
| `CNR` | Corporate Room Nights | **Corporate** |
| `CGR` | Corporate Group | MICE |
| `CNI` | Conference / Incentive Group | MICE |
| `EVEN` | Event Demand | MICE |
| `SMERF` | Social, Military, Educational, Religious, Fraternal (groups) | Leisure Group |

> **Trap:** "Corporate" as a macro-group is **only `CSR` + `CNR`**. The
> corporate-*sounding* `CGR` and `CNI` are classified as **MICE** (Meetings,
> Incentives, Conferences, Events), not Corporate.

### Channel codes (`channel_code`)

| Code | Full form | Channel group |
|---|---|---|
| `WEB` | Web / OTA Web | Digital |
| `REC` | Direct Reservations / Brand Web | Direct |
| `EMA` | Email / Central Reservations | Offline |
| `WAL` | Walk-in | Offline |

### Status values (`reservation_status`)

| Value | Meaning |
|---|---|
| `Reserved` | Active, live booking (counts toward OTB). |
| `Cancelled` | Cancelled booking (excluded from OTB; counted only for cancellation questions). |

---

## Abbreviations glossary (say these out loud)

| Term | Full form / meaning |
|---|---|
| **ADR** | Average Daily Rate — price per room per night. |
| **OTB** | On The Books — live future business (`Reserved` + `stay_date ≥` as-of). |
| **STLY** | Same Time Last Year — the past comparison window. |
| **OTA** | Online Travel Agency. |
| **MICE** | Meetings, Incentives, Conferences, Events. |
| **SMERF** | Social, Military, Educational, Religious, Fraternal. |
| **FIT** | Free Independent Traveller. |
| **BAR** | Best Available Rate / Retail. |
| **Room night** | One room occupied for one night (`SUM(number_of_spaces)`). |
| **Grain** | Level of detail of one row (here: one reservation × one stay date). |

---

## Key numbers (anchor `2026-06-11`)

| Metric | Value |
|---|---|
| Total reservations (distinct bookings) | 250 |
| Total stay rows | 516 |
| Current reservations (arrival ≤ 180 days) | 150 |
| Last-year reservations | 100 |
| Cancelled reservations | 20 |
| OTB room nights | 649 |
| OTB room revenue (before tax) | $117,566 |
| OTB total revenue (before tax) | $126,458 |
| STLY room nights | 340 |
| STLY total revenue (before tax) | $70,972 |
| ADR by room type | EX $248.53 · KS $188.21 · TB $178.50 |
| Physical capacity | 98 rooms (EX 26 + KS 52 + TB 20) |
