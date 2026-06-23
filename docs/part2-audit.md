# Part 2 raw extract audit

**Audit date:** 2026-06-11  
**Dataset as-of date:** 2026-06-11 (`dataset_metadata.as_of_date`)  
**Result:** **PASS**

---

## Diagnostic (verify re-pull)

| Check | Result |
|---|---|
| Verify scalars stable run-to-run | Yes — `total_stay_rows` 516, anchor 2026-06-11 unchanged across re-pulls |
| Prior reservation scrape anchor | 2026-06-10 (stale) |
| Prior raw stay-row total | 549 |
| Action taken | Re-scraped reservations + lookups, then verify back-to-back |

---

## 549 vs 516 reconciliation

These are **not** total-vs-windowed variants of the same snapshot:

| Number | What it counts | When |
|---|---|---|
| **549** | `total_stay_rows` — fact grain (reservation × stay_date) | 2026-06-10 reservation scrape |
| **516** | `total_stay_rows` — same metric on `/verify` | 2026-06-11 anchor (daily regeneration) |

The site regenerates data daily. After aligning both scrapes to **2026-06-11**, raw stay rows and verify `total_stay_rows` both equal **516**.

**649** is `otb_room_nights` (`SUM(number_of_spaces)` for Reserved, `stay_date ≥ anchor`) — a different metric, not stay-row count. The stale brief figure **455** is not used for validation.

---

## Counts (from aligned raw JSON)

| Check | Raw count | Verify / expected | Match |
|---|---:|---:|---|
| Distinct `reservation_id` | 250 | 250 | Yes |
| Total stay rows (`sum(len(stay_rows))`) | 516 | 516 | Yes |
| `room_type_lookup` | 3 | 3 | Yes |
| `market_code_lookup` | 10 | 10 | Yes |
| `channel_code_lookup` | 4 | 4 | Yes |
| Cancelled reservations | 20 | 20 | Yes |
| Missing `detail` | 0 | — | Yes |
| Missing `stay_rows` | 0 | — | Yes |
| `nights` ≠ `len(stay_rows)` | 0 | — | Yes |

**List header:** `250 reservations · book as of 2026-06-11`

---

## Spot-checks (grain)

| Booking | Type | Expected | Observed |
|---|---|---|---|
| **R0001** | Single-room, 3-night | 3 stay rows (not 1 row with nights=3); `number_of_spaces=1` | 3 rows; spaces=1 |
| **R0016** | Cancelled, 1-night, 2 rooms | 1 stay row; `cancellation_datetime` set | 1 row; `2026-04-27T12:00:00Z`; spaces=2 |
| **R0010** | Multi-room (`number_of_spaces=12`) | 4 stay rows; spaces preserved on each row | 4 rows; spaces=12 each |

> Note: Sample IDs from the 2026-06-10 exploration doc (e.g. R0002 cancelled, R0003 multi-room) differ on the 2026-06-11 dataset due to daily regeneration. The three booking **types** above were verified on the aligned scrape.

---

## Artifacts

| File | Contents |
|---|---|
| [`data/raw_reservations.json`](../data/raw_reservations.json) | List + detail + `stay_rows`; `dataset_metadata.as_of_date` |
| [`data/raw_lookups.json`](../data/raw_lookups.json) | Reference lookups (3 / 10 / 4) |
| [`data/raw_verify.json`](../data/raw_verify.json) | `/verify` page bundle |
| [`data/verify.raw_text`](../data/verify.raw_text) | Verify page plain text |
| [`data/verify_targets.json`](../data/verify_targets.json) | Parsed verify scalars |

Refresh verify only (no reservation re-scrape):

```bash
python -m etl.scrape_verify
```

Full aligned re-scrape:

```bash
python -m etl.extract
python -m etl.scrape_verify
```

---

## PASS / FAIL

**PASS** — 250 reservations, 516 stay rows matching verify for anchor 2026-06-11, lookups 3/10/4, grain spot-checks OK, no missing detail pages, no pagination gap.

Proceed to Part 3 transform.
