---
name: same-time-last-year
description: Use when comparing current OTB position to STLY and deciding if the gap is opportunity or concern.
---

# Same time last year (STLY)

## When to use

Load when the GM asks "how do we compare to last year?", "are we ahead or behind STLY?", or whether the gap is volume, rate, or mix.

## Tools to call

- `stly_comparison` — OTB vs STLY room nights and revenue with percent change.
- `revenue_on_books(group_by="month")` — where the gap sits by month.
- `segment_mix(dimension="macro_group")` — mix shift retail vs corporate vs MICE.
- Optional: `segment_mix(dimension="market_code", month="YYYY-MM")` for a specific month vs overall mix.

## Comparison baselines

- **STLY window:** Past reserved stays with `stay_date < as_of - 180 days` — not calendar year-over-year. Compare like the tool compares; do not invent a different STLY.
- **Nights vs revenue gap:** Ahead on nights, behind on revenue → rate or mix dilution. Behind on nights, ahead on revenue → fewer but higher-value rooms.
- **Month concentration:** A strong headline STLY beat may hide a weak peak month — check `revenue_on_books` by month.
- **Capacity:** 98 rooms — percentage gains have a ceiling; large night gaps may still be achievable, small gaps may be noise.

## Interpretation

**Healthy:** Ahead on both nights and revenue, or ahead on revenue with flat nights (rate improvement). Mix stable or shifting toward higher-ADR segments.

**Concerning:** Behind on both metrics — structural demand shortfall. Ahead on nights but behind on revenue — filling with discounted or OTA/group business. Behind on nights but "ahead" on revenue only because of one large group at low ADR — check segment mix.

**Why it matters to a GM:** STLY is the forward booking curve benchmark. Being behind with limited weeks left to pick up is an revenue-management emergency; being ahead with weak pace is a hold-rate signal.

## Heuristics

- Always cite both **room nights** and **revenue** percent change from `stly_comparison`.
- Gap of <5% on either metric may be noise; >10% warrants a named driver from `segment_mix`.
- STLY is not "last calendar year same month" — if the GM expects calendar YoY, state the tool's window and the limitation.
- Pair STLY with `whats_changed` — ahead on STLY but negative net pickup means the lead is eroding.

## Trap

**Treating STLY as calendar YoY or as OTB for the same calendar dates last year.** The tool uses a fixed backward stay window. Narrating "July 2025 vs July 2024" without checking month filters misleads the GM.

## Recommendation levers

1. **Behind on volume:** Segment-targeted stimulation on weak months; release group allotments if pickup is slow.
2. **Behind on revenue, OK on nights:** Rate fence — raise BAR, reduce promo depth; check OTA parity.
3. **Ahead on STLY:** Hold or test rate increase on compression dates; do not discount into strength.

## Briefing scaffold

> **Headline:** OTB is [ahead/behind] STLY by [X]% on nights and [Y]% on revenue.
> **Drivers:** [Month or segment explaining the gap]
> **Risk:** [Eroding pickup / mix dilution / peak month hole]
> **Action:** [Rate hold, targeted fill, or mix shift lever]
