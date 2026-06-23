# Data Model

Documentation for the hackathon reservation dataset: schema, grain, field semantics, and how to count correctly. Source of truth for **live numbers** is the data site verify page (see [GROUND_TRUTH.md](./GROUND_TRUTH.md)).

**Data site:** https://otel-hackathon-data-site.vercel.app  
**Database:** `postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon`  
**Schema:** [`schema.sql`](../schema.sql)

---

## Overview

Four Postgres tables, populated by scraping the data site (ETL not yet built):

| Table | Role | Site source |
|---|---|---|
| `reservations_hackathon` | Fact table — one row per reservation × stay_date | List + detail pages |
| `room_type_lookup` | Room type codes | `/reference` |
| `market_code_lookup` | Market / segment codes | `/reference` |
| `channel_code_lookup` | Booking channel codes | `/reference` |

The site is **client-rendered** (JavaScript). A plain HTTP fetch returns an empty shell; a real browser (Playwright) is required. Data is **regenerated daily** and is forward-looking from “today” (anchor date on verify page).

---

## Grain (most important concept)

`reservations_hackathon` is **not** one row per reservation.

**Grain: one row per reservation × stay_date**

- A 3-night stay → **3 fact rows** (one per night).
- A reservation with multiple rooms → each row carries `number_of_spaces` (room count for that night).
- Primary key: `reservation_stay_id` (auto-generated on load).
- Natural uniqueness: `(reservation_id, stay_date)`.

### Worked example: R0003

From the detail page (2 nights, 5 rooms, Reserved):

| Metric | Value |
|---|---|
| Reservations | 1 |
| Stay rows (fact rows) | 2 |
| Room nights | 2 × 5 = **10** |

Stay rows on the site:

| stay_date | daily_room_revenue_before_tax | daily_total_revenue_before_tax |
|---|---|---|
| 2026-08-19 | 925.00 | 1,015.00 |
| 2026-08-20 | 925.00 | 1,015.00 |

Here `925 = adr_room (185) × number_of_spaces (5)`.

---

## `number_of_spaces`

- **Meaning:** Number of **rooms** booked on that reservation for that stay date (“spaces” = rooms in this dataset).
- **On the list page:** Shown as column **Rooms**.
- **Room nights:** Sum spaces across stay rows after applying business filters (status, date, etc.):

```sql
SUM(number_of_spaces)  -- over filtered stay rows
```

Do **not** use `COUNT(*)` or `COUNT(DISTINCT reservation_id)` when the question asks for room nights.

---

## Counting cheat sheet

| Business question | Correct approach | Common mistake |
|---|---|---|
| How many **reservations**? | `COUNT(DISTINCT reservation_id)` | `COUNT(*)` on fact table |
| How many **stay rows** / fact rows? | `COUNT(*)` on `reservations_hackathon` | Treating as reservations |
| How many **room nights**? | `SUM(number_of_spaces)` on filtered stay rows | Ignoring multi-room bookings |
| Revenue for a period | `SUM(daily_*_revenue_before_tax)` on filtered stay rows | Summing `adr_room` |

---

## Revenue fields

Two numeric columns on each stay row (from detail page **Stay rows** table):

### `daily_room_revenue_before_tax`

- Room revenue for **that stay_date** row, before tax.
- On observed rows: `daily_room_revenue_before_tax ≈ adr_room × number_of_spaces` (e.g. R0001: 226 × 1 = 226; R0003: 185 × 5 = 925).
- Use when the question is specifically about **room revenue** or room-only ADR.

### `daily_total_revenue_before_tax`

- **Total** revenue for that stay_date row, before tax.
- Always **≥** `daily_room_revenue_before_tax` on sampled rows.
- Brief describes this as including room revenue plus synthetic package / breakfast effects (e.g. R0001: 244 vs 226 → +18/night; R0003: 1,015 vs 925 → +90/night for 5 rooms).
- Use for broad **total revenue** questions (“revenue on the books”, total OTB, etc.) unless the question explicitly asks for room-only.

### `adr_room`

- Reservation-level room ADR; **repeated** on every stay row for the same reservation.
- Verify-page ADR by room type is a separate aggregate (see GROUND_TRUTH); do not assume it equals `AVG(adr_room)`.

---

## Date fields

| Field | Type | Meaning |
|---|---|---|
| `stay_date` | date | The **night** represented by this fact row |
| `arrival_date` | date | Check-in date |
| `departure_date` | date | Check-out date — guest stays **up to but not including** this date |
| `create_datetime` | timestamptz | When the reservation was **booked** |
| `cancellation_datetime` | timestamptz, nullable | When cancelled; null / “—” for Reserved |

### Which date to use

| Question type | Primary date field |
|---|---|
| Revenue / room nights **by month or stay period** | `stay_date` |
| On-the-books for **future stays** | `stay_date` (verify OTB uses `stay_date ≥ anchor_date`) |
| **Booking pace**, pickup, “what was booked recently” | `create_datetime` |
| Cancellations **in a calendar period** | `cancellation_datetime` (filter `reservation_status = 'Cancelled'`) |
| Lead time, arrival patterns | `arrival_date` vs `create_datetime` (`lead_time` is precomputed days between them) |
| Length of stay window | `arrival_date`, `departure_date`, or `nights` |

Using the wrong date produces plausible-looking but **wrong** answers (e.g. booking pace by `stay_date` instead of `create_datetime`).

---

## Cancellations

- **`reservation_status`:** `Reserved` or `Cancelled` (observed values on the site).
- Cancelled reservations **still appear** in the fact table with their stay rows and revenue columns populated on the detail page (e.g. R0002).
- **`cancellation_datetime`:** Set for Cancelled (e.g. R0002: `2026-05-28T12:00:00Z`); shown as “—” when Reserved.
- **Default for OTB / forward revenue:** Exclude `Cancelled` unless the question is about cancellations or historical booked-and-cancelled business.
- Verify page OTB metrics explicitly filter **`Reserved`** and **`stay_date ≥ anchor_date`**.

Counting cancelled **reservations** (not stay rows):

```sql
COUNT(DISTINCT reservation_id)
WHERE reservation_status = 'Cancelled'
```

For “how much was cancelled in June”, filter by `cancellation_datetime` in June, not `stay_date`.

---

## List page vs detail page (scrape map)

Future ETL must combine list and detail views.

### List page (`/reservations`)

- **Pagination:** Client-side **Next → / ← Prev**; 100 rows per page; 3 pages → **250 reservations** total (as of 2026-06-10). Do **not** use `?page=` URL query params — they do not change the page.
- **Header:** `{N} reservations · book as of {anchor_date}`

| Site column | Schema field |
|---|---|
| Reservation | `reservation_id` |
| Arrival | `arrival_date` |
| Departure | `departure_date` |
| Nights | `nights` |
| Status | `reservation_status` |
| Market | `market_code` |
| Channel | `channel_code` |
| Room | `space_type` |
| Rooms | `number_of_spaces` |
| ADR | `adr_room` |
| Lead | `lead_time` |

### Detail page only (`/reservations/<id>`)

| Field | Notes |
|---|---|
| `create_datetime` | ISO timestamp |
| `cancellation_datetime` | “—” if not cancelled |
| `guest_country` | e.g. ES, NL, IE |
| `is_block` | boolean |
| `is_walk_in` | boolean |
| `source_name` | e.g. Brand website, Booking.com |
| `rate_plan_code` | e.g. CORP10BB, GROUPBB, FITBB |
| `company_name` | nullable |
| `travel_agent_name` | nullable |

### Stay rows table (detail only)

One row per night → maps 1:1 to fact table rows:

| Site column | Schema field |
|---|---|
| stay_date | `stay_date` |
| daily_room_revenue_before_tax | `daily_room_revenue_before_tax` |
| daily_total_revenue_before_tax | `daily_total_revenue_before_tax` |

List-level fields repeat on each stay row for the same reservation when loaded into the fact table.

---

## Lookup tables

Join keys from [`schema.sql`](../schema.sql):

- `reservations_hackathon.space_type` → `room_type_lookup.space_type`
- `reservations_hackathon.market_code` → `market_code_lookup.market_code`
- `reservations_hackathon.channel_code` → `channel_code_lookup.channel_code`

Full reference values and row counts: [GROUND_TRUTH.md](./GROUND_TRUTH.md).

---

## Sample reservations (from site exploration)

### R0001 — Reserved, 3 nights, 1 room

- Arrival 2026-07-23, departure 2026-07-26, CSR / REC / KS
- 3 stay rows; daily room 226.00, daily total 244.00 each night

### R0002 — Cancelled, 2 nights, 1 room

- `cancellation_datetime`: 2026-05-28T12:00:00Z
- 2 stay rows still shown with revenue (206.00 room / 224.00 total per night)

### R0003 — Reserved, block, 2 nights, 5 rooms

- `is_block`: true, `company_name`: TechSummit
- 2 stay rows; daily room 925.00, daily total 1,015.00 per night

---

## Open questions

Do not assume answers to these until confirmed during ETL or from site source:

1. **`current_reservations` / `last_year_reservations`** — Verify reports 150 / 100 split but does not define the rule (arrival year vs stay year vs anchor-relative).
2. **`stly_*` metrics** — Labelled “last_year, Reserved”; exact date alignment unknown.
3. **Verify ADR by room type** — Formula not specified (weighted by room nights vs other).
4. **`daily_total_revenue` composition** — Uplift over room revenue observed but package rules not documented on the site.
5. **Brief vs live row counts** — Brief §15 cites 455 fact rows; live verify (2026-06-10) reports 549 stay rows and 250 reservations (see GROUND_TRUTH).
6. **Cancelled rows in `total_stay_rows`** — Likely included; confirm at load time against verify.
