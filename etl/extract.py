"""Extract raw reservation and lookup data from the hackathon data site."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from etl import config

RESERVATION_ID_RE = re.compile(r"^R\d+$", re.IGNORECASE)
AS_OF_DATE_RE = re.compile(r"book as of (\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def polite_delay(page: Page) -> None:
    page.wait_for_timeout(config.REQUEST_DELAY_MS)


def parse_as_of_date(list_header: str) -> str | None:
    match = AS_OF_DATE_RE.search(list_header)
    return match.group(1) if match else None


def dataset_metadata(scraped_at: str, as_of_date: str | None) -> dict[str, str | None]:
    return {"as_of_date": as_of_date, "scraped_at": scraped_at}


def reservation_sort_key(reservation_id: str) -> tuple[int, str]:
    match = re.match(r"^R(\d+)$", reservation_id)
    if match:
        return (int(match.group(1)), reservation_id)
    return (sys.maxsize, reservation_id)


def write_json(path: str | Path, data: object) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_table(page: Page, table_locator) -> tuple[list[str], list[dict[str, str]]]:
    headers = [h.strip() for h in table_locator.locator("thead th").all_inner_texts()]
    rows: list[dict[str, str]] = []
    for tr in table_locator.locator("tbody tr").all():
        cells = [c.strip() for c in tr.locator("td").all_inner_texts()]
        if not cells or (len(cells) == 1 and cells[0].lower().startswith("loading")):
            continue
        row: dict[str, str] = {}
        for i, header in enumerate(headers):
            if i >= len(cells):
                break
            key = header if header else f"_col_{i}"
            row[key] = cells[i]
        if row:
            rows.append(row)
    return headers, rows


def row_value(row: dict[str, str], *names: str) -> str:
    lowered = {k.lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value.strip()
    return ""


def reservation_id_from_list_row(row: dict[str, str]) -> str:
    for value in row.values():
        if RESERVATION_ID_RE.match(value.strip()):
            return value.strip().upper()
    reservation = row_value(row, "Reservation", "RESERVATION")
    return reservation.upper() if reservation else ""


def wait_for_list_loaded(page: Page) -> None:
    loading = page.get_by_text("Loading the book of business…", exact=False)
    if loading.count():
        loading.first.wait_for(state="hidden", timeout=config.ELEMENT_TIMEOUT_MS)
    page.locator("main table tbody tr").first.wait_for(
        state="visible", timeout=config.ELEMENT_TIMEOUT_MS
    )
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('main table tbody tr');
            if (!rows.length) return false;
            const first = rows[0].cells[0]?.innerText?.trim() || '';
            return /^R\\d+$/.test(first);
        }""",
        timeout=config.ELEMENT_TIMEOUT_MS,
    )


def get_list_header(page: Page) -> str:
    header = page.locator("main h1 + p").first
    if header.count():
        return header.inner_text().strip()
    return page.locator("main p").first.inner_text().strip()


def parse_list_page(page: Page) -> list[dict[str, str]]:
    table = page.locator("main table").first
    _, rows = parse_table(page, table)
    return rows


def get_page_indicator(page: Page) -> str | None:
    for el in page.locator("main *").all():
        text = el.inner_text().strip()
        if re.fullmatch(r"Page \d+ of \d+", text):
            return text
    return None


def click_next_page(page: Page) -> bool:
    next_btn = page.get_by_role("button", name=re.compile(r"Next", re.I))
    if not next_btn.count() or next_btn.is_disabled():
        return False
    before = get_page_indicator(page)
    next_btn.click()
    polite_delay(page)
    wait_for_list_loaded(page)
    after = get_page_indicator(page)
    if before and after and before == after:
        return False
    return True


def scrape_all_list_rows(page: Page) -> tuple[str, list[dict[str, str]]]:
    page.goto(f"{config.BASE_URL}/reservations", timeout=config.NAVIGATION_TIMEOUT_MS)
    wait_for_list_loaded(page)
    polite_delay(page)

    header = get_list_header(page)
    all_rows: list[dict[str, str]] = []
    seen_pages: set[str | None] = set()

    for _ in range(config.MAX_LIST_PAGES):
        page_key = get_page_indicator(page)
        if page_key in seen_pages:
            break
        seen_pages.add(page_key)

        rows = parse_list_page(page)
        all_rows.extend(rows)

        if not click_next_page(page):
            break

    deduped: dict[str, dict[str, str]] = {}
    for row in all_rows:
        reservation_id = reservation_id_from_list_row(row)
        if RESERVATION_ID_RE.match(reservation_id):
            deduped[reservation_id] = row

    sorted_rows = sorted(
        deduped.values(), key=lambda r: reservation_sort_key(reservation_id_from_list_row(r))
    )
    return header, sorted_rows


def wait_for_detail_loaded(page: Page, reservation_id: str) -> None:
    loading_text = f"Loading reservation {reservation_id}"
    loading = page.get_by_text(loading_text, exact=False)
    if loading.count():
        loading.first.wait_for(state="hidden", timeout=config.ELEMENT_TIMEOUT_MS)
    page.locator("main h1").first.wait_for(
        state="visible", timeout=config.ELEMENT_TIMEOUT_MS
    )
    page.get_by_role("heading", name="Reservation fields").wait_for(
        state="visible", timeout=config.ELEMENT_TIMEOUT_MS
    )


def parse_detail_fields(page: Page) -> dict[str, str]:
    fields: dict[str, str] = {}
    headings = page.get_by_role("heading", name="Reservation fields")
    if not headings.count():
        return fields

    container = headings.first.locator("xpath=following-sibling::*[1]")
    dts = container.locator("dt")
    for i in range(dts.count()):
        dt = dts.nth(i)
        term = dt.inner_text().strip()
        dd = dt.locator("xpath=following-sibling::dd[1]")
        fields[term] = dd.inner_text().strip() if dd.count() else ""
    return fields


def parse_stay_rows(page: Page) -> list[dict[str, str]]:
    stay_heading = page.locator("main h2").filter(has_text="Stay rows")
    if not stay_heading.count():
        return []

    table = stay_heading.first.locator("xpath=following::table[1]")
    if not table.count():
        return []

    _, rows = parse_table(page, table)
    rows.sort(key=lambda r: row_value(r, "stay_date", "STAY_DATE"))
    return rows


def scrape_detail_once(page: Page, reservation_id: str) -> dict:
    page.goto(
        f"{config.BASE_URL}/reservations/{reservation_id}",
        timeout=config.NAVIGATION_TIMEOUT_MS,
    )
    wait_for_detail_loaded(page, reservation_id)
    polite_delay(page)

    detail = parse_detail_fields(page)
    stay_rows = parse_stay_rows(page)
    return {"detail": detail, "stay_rows": stay_rows}


def scrape_detail_with_retry(
    page: Page, reservation_id: str, expected_nights: int
) -> dict:
    backoffs = [1, 2, 4]
    last_error: Exception | None = None

    for attempt in range(config.DETAIL_MAX_RETRIES):
        try:
            result = scrape_detail_once(page, reservation_id)
            detail = result["detail"]
            stay_rows = result["stay_rows"]

            if not detail:
                raise ValueError("detail fields empty")
            if expected_nights > 0 and len(stay_rows) == 0:
                raise ValueError("stay rows missing")
            if expected_nights > 0 and len(stay_rows) != expected_nights:
                raise ValueError(
                    f"expected {expected_nights} stay rows, got {len(stay_rows)}"
                )
            return result
        except Exception as exc:
            last_error = exc
            if attempt < config.DETAIL_MAX_RETRIES - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])

    raise RuntimeError(
        f"Failed to scrape detail for {reservation_id} after "
        f"{config.DETAIL_MAX_RETRIES} attempts: {last_error}"
    )


def wait_for_reference_loaded(page: Page) -> None:
    for name in (
        "room_type_lookup",
        "market_code_lookup",
        "channel_code_lookup",
    ):
        page.get_by_role("heading", name=name, exact=True).wait_for(
            state="visible", timeout=config.ELEMENT_TIMEOUT_MS
        )
        heading = page.get_by_role("heading", name=name, exact=True)
        table = heading.locator("xpath=following::table[1]")
        table.locator("tbody tr").first.wait_for(
            state="visible", timeout=config.ELEMENT_TIMEOUT_MS
        )


def scrape_reference(page: Page) -> dict[str, list[dict[str, str]]]:
    page.goto(f"{config.BASE_URL}/reference", timeout=config.NAVIGATION_TIMEOUT_MS)
    wait_for_reference_loaded(page)
    polite_delay(page)

    lookups: dict[str, list[dict[str, str]]] = {}
    for name in (
        "room_type_lookup",
        "market_code_lookup",
        "channel_code_lookup",
    ):
        heading = page.get_by_role("heading", name=name, exact=True)
        table = heading.locator("xpath=following::table[1]")
        _, rows = parse_table(page, table)
        sort_key = config.LOOKUP_SORT_KEYS[name]
        rows.sort(key=lambda r: row_value(r, sort_key))
        lookups[name] = rows
    return lookups


def build_reservations_output(
    list_header: str,
    list_rows: list[dict[str, str]],
    details_by_id: dict[str, dict],
) -> dict:
    reservations = []
    for list_row in list_rows:
        reservation_id = reservation_id_from_list_row(list_row)
        detail_payload = details_by_id[reservation_id]
        reservations.append(
            {
                "reservation_id": reservation_id,
                "list": list_row,
                "detail": detail_payload["detail"],
                "stay_rows": detail_payload["stay_rows"],
            }
        )

    scraped_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    as_of_date = parse_as_of_date(list_header)
    return {
        "source": config.BASE_URL,
        "scraped_at": scraped_at,
        "list_header": list_header,
        "dataset_metadata": dataset_metadata(scraped_at, as_of_date),
        "reservations": reservations,
    }


def build_lookups_output(
    lookups: dict[str, list[dict[str, str]]],
    *,
    as_of_date: str | None,
    scraped_at: str | None = None,
) -> dict:
    scraped_at = scraped_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "source": config.BASE_URL,
        "scraped_at": scraped_at,
        "dataset_metadata": dataset_metadata(scraped_at, as_of_date),
        **lookups,
    }


def print_summary(
    list_header: str,
    reservation_count: int,
    stay_row_count: int,
    lookup_counts: dict[str, int],
    reservations: list[dict],
) -> int:
    print("\n=== Extract summary ===")
    mismatches = 0

    checks = [
        ("Reservations scraped", reservation_count, "total_reservations"),
        ("Total stay rows", stay_row_count, "total_stay_rows"),
        ("room_type_lookup rows", lookup_counts["room_type_lookup"], "room_type_lookup"),
        (
            "market_code_lookup rows",
            lookup_counts["market_code_lookup"],
            "market_code_lookup",
        ),
        (
            "channel_code_lookup rows",
            lookup_counts["channel_code_lookup"],
            "channel_code_lookup",
        ),
    ]

    for label, actual, key in checks:
        expected = config.EXPECTED[key]
        line = f"{label + ':':<28} {actual:>4}  (expected {expected})"
        print(line)
        if actual != expected:
            mismatches += 1
            print(f"  *** MISMATCH *** {label}: got {actual}, expected {expected}")

    print(f"List header: {list_header}")

    if config.EXPECTED_ANCHOR_DATE not in list_header:
        print(
            f"\nWARNING: List header does not contain anchor date "
            f"{config.EXPECTED_ANCHOR_DATE}. GROUND_TRUTH expectations may be stale."
        )

    print("\n--- Sample: first reservation ---")
    if reservations:
        print(json.dumps(reservations[0], indent=2, ensure_ascii=True))

    sample_multi = next(
        (
            r
            for r in reservations
            if row_value(r.get("list", {}), "Rooms", "ROOMS") not in ("1", "")
        ),
        None,
    )
    if sample_multi and sample_multi["reservation_id"] != reservations[0]["reservation_id"]:
        print(f"\n--- Sample: multi-room ({sample_multi['reservation_id']}) ---")
        print(json.dumps(sample_multi, indent=2, ensure_ascii=True))

    if mismatches:
        print(f"\n*** {mismatches} count mismatch(es) vs GROUND_TRUTH.md ***")
    else:
        print("\nAll counts match GROUND_TRUTH.md.")

    return 1 if mismatches else 0


def run_extract() -> int:
    print("Starting extract from", config.BASE_URL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)

        print("Scraping reservation list...")
        list_header, list_rows = scrape_all_list_rows(page)
        print(f"  List header: {list_header}")
        print(f"  List rows collected: {len(list_rows)}")

        print("Scraping reservation details...")
        details_by_id: dict[str, dict] = {}
        for i, list_row in enumerate(list_rows, start=1):
            reservation_id = reservation_id_from_list_row(list_row)
            nights_raw = row_value(list_row, "Nights", "NIGHTS") or "0"
            try:
                expected_nights = int(nights_raw)
            except ValueError:
                expected_nights = 0

            if i % 25 == 0 or i == len(list_rows):
                print(f"  Detail progress: {i}/{len(list_rows)}")

            details_by_id[reservation_id] = scrape_detail_with_retry(
                page, reservation_id, expected_nights
            )

        print("Scraping reference lookups...")
        lookups = scrape_reference(page)

        browser.close()

    reservations_payload = build_reservations_output(list_header, list_rows, details_by_id)
    as_of_date = reservations_payload["dataset_metadata"]["as_of_date"]
    lookups_payload = build_lookups_output(
        lookups,
        as_of_date=as_of_date,
        scraped_at=reservations_payload["scraped_at"],
    )

    write_json(config.OUTPUT_RESERVATIONS, reservations_payload)
    write_json(config.OUTPUT_LOOKUPS, lookups_payload)
    print(f"\nWrote {config.OUTPUT_RESERVATIONS}")
    print(f"Wrote {config.OUTPUT_LOOKUPS}")

    stay_row_count = sum(len(r["stay_rows"]) for r in reservations_payload["reservations"])
    lookup_counts = {
        "room_type_lookup": len(lookups_payload["room_type_lookup"]),
        "market_code_lookup": len(lookups_payload["market_code_lookup"]),
        "channel_code_lookup": len(lookups_payload["channel_code_lookup"]),
    }

    return print_summary(
        list_header,
        len(reservations_payload["reservations"]),
        stay_row_count,
        lookup_counts,
        reservations_payload["reservations"],
    )


def main() -> None:
    sys.exit(run_extract())


if __name__ == "__main__":
    main()
