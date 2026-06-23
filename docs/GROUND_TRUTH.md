# Ground Truth

Verification targets from the data site **verify page** and **reference page**, captured on **2026-06-10** (anchor date). Use these to validate a future ETL load.

**Verify page:** https://otel-hackathon-data-site.vercel.app/verify  
**Reference page:** https://otel-hackathon-data-site.vercel.app/reference

> The site footer states data is **regenerated daily** and forward-looking from “today”. Re-scrape `/verify` on the day you run ETL; numbers below apply to anchor date **2026-06-10** only.

---

## Anchor date

```json
"anchor_date": "2026-06-10"
```

List page header matches: `250 reservations · book as of 2026-06-10`.

---

## Three numbers people confuse (read this first)

The hackathon brief and verify page use several totals. **Do not compare them interchangeably.**

| Number | What it is | Live value (2026-06-10) | How to validate after load |
|---|---|---:|---|
| **250** | Distinct **reservations** (bookings) | 250 | `COUNT(DISTINCT reservation_id)` |
| **549** | **`total_stay_rows`** — fact-table rows at grain **reservation × stay_date** (includes cancelled and past nights) | 549 | `COUNT(*)` on `reservations_hackathon` |
| **514** | **`otb_room_nights`** — **room nights** on the books (Reserved, `stay_date ≥ anchor`); multi-room stays count each room | 514 | `SUM(number_of_spaces)` with OTB filters |
| **455** | **Stale brief figure** — outdated static count from [`what_do_i_want_to_do.md`](../what_do_i_want_to_do.md) §15; **not** reservations, **not** OTB room nights, **not** authoritative | — | **Ignore for validation**; use `/verify` on scrape day |

**Common mistakes:**

- Treating **455** as reservation count or stay-row count (wrong — brief is stale).
- Expecting **~513–514 stay rows** when verify’s stay-row total is **549** — ~514 is **OTB room nights**, a different metric.
- Using `COUNT(*)` on the fact table when the question asks for **bookings** (use distinct `reservation_id`) or **room nights** (use `SUM(number_of_spaces)`).

**Extract gate (Part 2):** 250 reservations, 549 stay rows summed from raw `stay_rows`, lookups 3 / 10 / 4. See [`part2-audit.md`](part2-audit.md).

---

## Lookup table row counts

| Table | Expected rows | Source |
|---|---|---|
| `room_type_lookup` | **3** | `/reference` |
| `market_code_lookup` | **10** | `/reference` |
| `channel_code_lookup` | **4** | `/reference` |

### `room_type_lookup`

| space_type | room_class | display_name | number_of_rooms |
|---|---|---|---|
| KS | Standard | Standard King | 52 |
| TB | Standard | Standard Twin | 20 |
| EX | Executive | Executive King | 26 |

### `market_code_lookup`

| market_code | market_name | macro_group |
|---|---|---|
| OTA | Online Travel Agency | Retail |
| BAR | Best Available Retail | Retail |
| PROM | Promotional Retail | Retail |
| FIT | Free Independent Traveller | Leisure |
| CSR | Corporate Negotiated | Corporate |
| CNR | Corporate Room Nights | Corporate |
| CNI | Conference / Incentive Group | MICE |
| CGR | Corporate Group | MICE |
| EVEN | Event Demand | MICE |
| SMERF | SMERF Group | Leisure Group |

### `channel_code_lookup`

| channel_code | channel_name | channel_group |
|---|---|---|
| WEB | Web / OTA Web | Digital |
| REC | Direct Reservations / Brand Web | Direct |
| EMA | Email / Central Reservations | Offline |
| WAL | Walk-in | Offline |

---

## Verify checksums (2026-06-10)

Definitions below are copied from verify page section headings. Values from **Raw JSON** on `/verify`.

### Row counts

| Metric | Value | Definition (from verify page) |
|---|---|---|
| `total_reservations` | **250** | Count of distinct reservations in the dataset |
| `total_stay_rows` | **549** | Count of rows in the fact table (reservation × stay_date). **Not** room nights; **not** the brief’s 455 |
| `current_reservations` | **150** | *(Label only — split rule not defined on site)* |
| `last_year_reservations` | **100** | *(Label only — split rule not defined on site)* |
| `cancelled_reservations` | **24** | Reservations with `Cancelled` status |

**Check:** `current_reservations` + `last_year_reservations` = 250 = `total_reservations`.

### On the books (current, Reserved, stay_date ≥ today)

Anchor “today” = **2026-06-10**.

| Metric | Value | Definition |
|---|---|---|
| `otb_room_nights` | **514** | `SUM(number_of_spaces)` on Reserved stays with `stay_date ≥ anchor` — **not** `total_stay_rows` (549) |
| `otb_room_revenue_before_tax` | **96,130.00** | |
| `otb_total_revenue_before_tax` | **102,574.00** | |

**Intended filters:** `reservation_status = 'Reserved'` AND `stay_date >= '2026-06-10'`. The meaning of **“current”** beyond that is not fully specified on the verify page.

### Same time last year (last_year, Reserved)

| Metric | Value |
|---|---|
| `stly_room_nights` | **413** |
| `stly_total_revenue_before_tax` | **82,066.00** |

**Intended filters:** `reservation_status = 'Reserved'` plus a **“last_year”** window — exact date logic not documented on the site.

### ADR by room type (current, Reserved)

| space_type | ADR |
|---|---|
| KS | **192.78** |
| TB | **178.87** |
| EX | **251.63** |

Formula not specified (likely revenue-weighted; treat as verify target, not a assumed SQL formula).

### On-the-books room nights by market code

Summing to **514** (= `otb_room_nights`).

| market_code | room_nights |
|---|---|
| EVEN | 96 |
| CGR | 85 |
| OTA | 82 |
| CNI | 63 |
| CSR | 49 |
| BAR | 35 |
| CNR | 33 |
| SMERF | 28 |
| PROM | 25 |
| FIT | 18 |

---

## Raw JSON (verify page)

```json
{
  "anchor_date": "2026-06-10",
  "total_reservations": 250,
  "total_stay_rows": 549,
  "current_reservations": 150,
  "last_year_reservations": 100,
  "cancelled_reservations": 24,
  "otb_room_nights": 514,
  "otb_total_revenue_before_tax": 102574,
  "otb_room_revenue_before_tax": 96130,
  "stly_room_nights": 413,
  "stly_total_revenue_before_tax": 82066,
  "adr_by_room_type": {
    "KS": 192.78,
    "TB": 178.87,
    "EX": 251.63
  },
  "otb_room_nights_by_market": {
    "CSR": 49,
    "EVEN": 96,
    "CNI": 63,
    "OTA": 82,
    "BAR": 35,
    "CGR": 85,
    "PROM": 25,
    "CNR": 33,
    "FIT": 18,
    "SMERF": 28
  }
}
```

---

## Suggested post-load SQL checks

Run after ETL. Adjust filters once “current” / “last_year” / STLY rules are confirmed.

### Row counts

```sql
-- total_stay_rows → expect 549
SELECT COUNT(*) FROM reservations_hackathon;

-- total_reservations → expect 250
SELECT COUNT(DISTINCT reservation_id) FROM reservations_hackathon;

-- cancelled_reservations → expect 24
SELECT COUNT(DISTINCT reservation_id)
FROM reservations_hackathon
WHERE reservation_status = 'Cancelled';

-- Lookup counts → expect 3, 10, 4
SELECT COUNT(*) FROM room_type_lookup;
SELECT COUNT(*) FROM market_code_lookup;
SELECT COUNT(*) FROM channel_code_lookup;
```

### OTB (partial — definition from verify heading)

```sql
-- otb_room_nights → expect 514
SELECT SUM(number_of_spaces)
FROM reservations_hackathon
WHERE reservation_status = 'Reserved'
  AND stay_date >= DATE '2026-06-10';

-- otb_room_revenue_before_tax → expect 96130.00
SELECT SUM(daily_room_revenue_before_tax)
FROM reservations_hackathon
WHERE reservation_status = 'Reserved'
  AND stay_date >= DATE '2026-06-10';

-- otb_total_revenue_before_tax → expect 102574.00
SELECT SUM(daily_total_revenue_before_tax)
FROM reservations_hackathon
WHERE reservation_status = 'Reserved'
  AND stay_date >= DATE '2026-06-10';
```

### OTB room nights by market (partial)

```sql
-- Example: EVEN → expect 96 (same OTB filters as above)
SELECT SUM(number_of_spaces)
FROM reservations_hackathon
WHERE reservation_status = 'Reserved'
  AND stay_date >= DATE '2026-06-10'
  AND market_code = 'EVEN';
```

### List scrape completeness

```sql
-- Should match total_reservations (250)
SELECT COUNT(DISTINCT reservation_id) FROM reservations_hackathon;

-- Reservations with wrong stay-row count vs nights (sanity check)
SELECT reservation_id, nights, COUNT(*) AS stay_rows
FROM reservations_hackathon
GROUP BY reservation_id, nights
HAVING COUNT(*) <> nights;
```

---

## Brief vs live discrepancy

The repo brief ([`what_do_i_want_to_do.md`](../what_do_i_want_to_do.md) §15) lists a static **455 rows** in `reservations_hackathon`. That figure is **stale** and must not be used as a load target.

| Metric | Brief §15 | Live verify (2026-06-10) | Notes |
|---|---|---|---|
| Reservations | *(not stated)* | **250** | `total_reservations` |
| Fact rows (stay rows) | **455** | **549** | `total_stay_rows` — brief undercounts vs current dataset |
| OTB room nights | *(not stated)* | **514** | `otb_room_nights` — often confused with stay-row count |
| Lookup rows | 3 / 10 / 4 | 3 / 10 / 4 ✓ | Unchanged |

**Authoritative for ETL validation:** live `/verify` on scrape day. After load, check **250** reservations, **549** stay rows, and **514** OTB room nights as **separate** checksums — plus lookups 3 / 10 / 4.

---

## Reservations list pagination (scrape completeness)

As of 2026-06-10:

| Page | Rows shown |
|---|---|
| 1 of 3 | 100 |
| 2 of 3 | 100 |
| 3 of 3 | 50 |
| **Total** | **250** |

Pagination is via **Next →** button (not URL query params).

---

## Open questions

1. **`current_reservations` (150) vs `last_year_reservations` (100)** — No on-site definition of the split; SQL filters TBD.
2. **`stly_*` metrics** — “last_year, Reserved” date window unspecified.
3. **`adr_by_room_type`** — Aggregation formula unspecified; match verify targets empirically.
4. **Whether `total_stay_rows` includes cancelled stay rows** — Likely yes (549 total vs 24 cancelled reservations); confirm after load.
5. **Daily regeneration** — Re-run verify on ETL day; all numbers above are for **2026-06-10** only.
