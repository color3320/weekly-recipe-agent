"""Scrape the hackathon /verify page only (no reservation re-scrape)."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from etl import config
from etl.extract import polite_delay, write_json

VERIFY_LOADING_TEXT = "Computing today's checksums"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def wait_for_verify_loaded(page: Page) -> None:
    loading = page.get_by_text(VERIFY_LOADING_TEXT, exact=False)
    if loading.count():
        loading.first.wait_for(state="hidden", timeout=config.ELEMENT_TIMEOUT_MS)
    page.get_by_role("heading", name="Verification targets").wait_for(
        state="visible", timeout=config.ELEMENT_TIMEOUT_MS
    )
    page.wait_for_function(
        """() => {
            const text = document.body.innerText || '';
            return text.includes('total_reservations') || text.includes('TOTAL_RESERVATIONS');
        }""",
        timeout=config.ELEMENT_TIMEOUT_MS,
    )


def extract_raw_json(page: Page) -> dict[str, Any] | None:
    details = page.locator("details")
    if details.count():
        details.first.evaluate("el => el.open = true")
    pre = page.locator("details pre, pre")
    if pre.count():
        try:
            return json.loads(pre.first.inner_text())
        except json.JSONDecodeError:
            pass
    match = re.search(r'\{[^{}]*"anchor_date"[\s\S]*\}', page.locator("main").inner_text())
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def scrape_verify_sections(page: Page) -> dict[str, list[dict[str, str]]]:
    """Capture label/value pairs grouped by verify section heading."""
    return page.evaluate(
        """() => {
            const sections = {};
            const headings = [...document.querySelectorAll('main h2')];
            for (const h2 of headings) {
                const name = h2.innerText.trim();
                if (!name) continue;
                const items = [];
                let el = h2.nextElementSibling;
                while (el && el.tagName !== 'H2') {
                    const labels = el.querySelectorAll('[class*="generic"], div');
                    // verify page uses paired label/value divs
                    const pairs = el.querySelectorAll('div');
                    const children = [...el.children];
                    for (let i = 0; i < children.length; i += 2) {
                        const labelEl = children[i];
                        const valueEl = children[i + 1];
                        if (!labelEl || !valueEl) continue;
                        const label = labelEl.innerText?.trim();
                        const value = valueEl.innerText?.trim();
                        if (label && value && !label.includes('\\n')) {
                            items.push({ label, value });
                        }
                    }
                    el = el.nextElementSibling;
                }
                if (items.length) sections[name] = items;
            }
            return sections;
        }"""
    )


def scrape_verify_page(page: Page) -> dict[str, Any]:
    page.goto(config.VERIFY_URL, timeout=config.NAVIGATION_TIMEOUT_MS)
    wait_for_verify_loaded(page)
    polite_delay(page)

    main_text = page.locator("main").inner_text()
    raw_json = extract_raw_json(page)
    sections = scrape_verify_sections(page)

    return {
        "source": config.BASE_URL,
        "url": config.VERIFY_URL,
        "scraped_at": utc_now_iso(),
        "raw_text": main_text,
        "raw_json": raw_json,
        "sections": sections,
    }


def _parse_number(value: str) -> int | float:
    cleaned = value.replace(",", "").strip()
    if "." in cleaned:
        return float(cleaned)
    return int(cleaned)


def parse_verify_targets(raw_verify: dict[str, Any]) -> dict[str, Any]:
    """Build Part 4 golden-test targets from raw_json and/or raw_text."""
    targets: dict[str, Any] = {
        "source": config.VERIFY_URL,
        "scraped_at": raw_verify.get("scraped_at"),
        "anchor_date": None,
        "scalars": {},
        "adr_by_room_type": {},
        "otb_room_nights_by_market": {},
    }

    raw_json = raw_verify.get("raw_json")
    if isinstance(raw_json, dict):
        targets["anchor_date"] = raw_json.get("anchor_date")
        scalar_keys = [
            "total_reservations",
            "total_stay_rows",
            "current_reservations",
            "last_year_reservations",
            "cancelled_reservations",
            "otb_room_nights",
            "otb_room_revenue_before_tax",
            "otb_total_revenue_before_tax",
            "stly_room_nights",
            "stly_total_revenue_before_tax",
        ]
        for key in scalar_keys:
            if key in raw_json:
                targets["scalars"][key] = raw_json[key]
        if "adr_by_room_type" in raw_json:
            targets["adr_by_room_type"] = raw_json["adr_by_room_type"]
        if "otb_room_nights_by_market" in raw_json:
            targets["otb_room_nights_by_market"] = raw_json["otb_room_nights_by_market"]
        return targets

    text = raw_verify.get("raw_text", "")
    anchor_match = re.search(r"as of (\d{4}-\d{2}-\d{2})", text, re.I)
    if anchor_match:
        targets["anchor_date"] = anchor_match.group(1)

    def grab_scalar(name: str) -> None:
        pattern = rf"{re.escape(name)}\s*\n\s*([\d,]+(?:\.\d+)?)"
        match = re.search(pattern, text, re.I)
        if match:
            targets["scalars"][name] = _parse_number(match.group(1))

    for key in (
        "total_reservations",
        "total_stay_rows",
        "current_reservations",
        "last_year_reservations",
        "cancelled_reservations",
        "otb_room_nights",
        "otb_room_revenue_before_tax",
        "otb_total_revenue_before_tax",
        "stly_room_nights",
        "stly_total_revenue_before_tax",
    ):
        grab_scalar(key)

    return targets


def print_checklist(targets: dict[str, Any], raw_verify: dict[str, Any]) -> None:
    print("\n=== Verify scrape summary ===")
    print(f"Saved raw:     {config.OUTPUT_VERIFY}")
    print(f"Saved targets: {config.OUTPUT_VERIFY_TARGETS}")
    print(f"Scraped at:    {targets.get('scraped_at')}")
    print(f"Anchor date:   {targets.get('anchor_date')}")

    scalars = targets.get("scalars", {})
    print("\n--- Scalars ---")
    for key in (
        "total_reservations",
        "total_stay_rows",
        "cancelled_reservations",
        "otb_room_nights",
        "otb_room_revenue_before_tax",
        "otb_total_revenue_before_tax",
        "stly_room_nights",
        "stly_total_revenue_before_tax",
    ):
        if key in scalars:
            print(f"  {key}: {scalars[key]}")

    adr = targets.get("adr_by_room_type", {})
    if adr:
        print("\n--- ADR by room type ---")
        for room, value in sorted(adr.items()):
            print(f"  {room}: {value}")

    markets = targets.get("otb_room_nights_by_market", {})
    if markets:
        print("\n--- OTB room nights by market ---")
        for code, value in sorted(markets.items(), key=lambda x: -x[1]):
            print(f"  {code}: {value}")

    excerpt = (raw_verify.get("raw_text") or "")[:400].replace("\n", " | ")
    print("\n--- Raw text excerpt ---")
    print(json.dumps(excerpt, ensure_ascii=True))

    print("\nPaste for Part 3 notes:")
    print(
        f"Verify anchor {targets.get('anchor_date')}: "
        f"{scalars.get('total_reservations')} reservations, "
        f"{scalars.get('total_stay_rows')} stay rows, "
        f"{scalars.get('otb_room_nights')} OTB room nights"
    )


def run_scrape_verify() -> int:
    print(f"Scraping verify page: {config.VERIFY_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(config.ELEMENT_TIMEOUT_MS)
        raw_verify = scrape_verify_page(page)
        browser.close()

    targets = parse_verify_targets(raw_verify)

    write_json(config.OUTPUT_VERIFY, raw_verify)
    write_json(config.OUTPUT_VERIFY_TARGETS, targets)

    raw_text = raw_verify.get("raw_text") or ""
    raw_text_path = Path(config.OUTPUT_VERIFY_RAW_TEXT)
    raw_text_path.parent.mkdir(parents=True, exist_ok=True)
    raw_text_path.write_text(raw_text, encoding="utf-8")

    print_checklist(targets, raw_verify)

    required = [
        "total_reservations",
        "total_stay_rows",
        "otb_room_nights",
        "otb_room_revenue_before_tax",
        "otb_total_revenue_before_tax",
        "stly_room_nights",
        "stly_total_revenue_before_tax",
        "cancelled_reservations",
    ]
    missing = [k for k in required if k not in targets.get("scalars", {})]
    if missing:
        print(f"\n*** WARNING: missing parsed scalars: {missing}")
        return 1
    if not targets.get("adr_by_room_type"):
        print("\n*** WARNING: adr_by_room_type breakdown missing")
    if not targets.get("otb_room_nights_by_market"):
        print("\n*** WARNING: otb_room_nights_by_market breakdown missing")

    print("\nVerify scrape complete.")
    return 0


def main() -> None:
    sys.exit(run_scrape_verify())


if __name__ == "__main__":
    main()
