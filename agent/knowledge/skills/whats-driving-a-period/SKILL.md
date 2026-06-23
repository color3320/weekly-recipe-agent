---
name: whats-driving-a-period
description: Use when explaining what is driving a month or forward period (segment mix, revenue concentration, recent change).
---

# What's driving a period

## When to use

Load when the GM asks "what's driving July?", "why is Q3 strong/weak?", or "where is the business coming from?" for a specific forward window.

## Tools to call

- `segment_mix(dimension="market_code", month="YYYY-MM")` — primary driver breakdown by segment.
- `segment_mix(dimension="macro_group", month="YYYY-MM")` — retail vs corporate vs MICE rollup.
- `revenue_on_books(group_by="month")` — month-level OTB totals for context.
- `whats_changed(days=7)` — recent bookings/cancellations affecting forward stays.
- Optional: `segment_mix(dimension="channel_code", month="YYYY-MM")` if the question is path vs segment.

## Comparison baselines

- **Within the month:** Top segments by revenue share vs room-night share — divergence signals rate/mix effect.
- **Vs full OTB:** Month share of total forward business — is this month overweight or underweight?
- **Vs STLY month:** Pair with `stly_comparison` and month-filtered `segment_mix` when the GM asks "vs last year."
- **Recent velocity:** `whats_changed` net room nights — is the month still building or stalling?
- **Capacity:** ~98 rooms; a single group block can dominate a weak month.

## Interpretation

**Healthy:** Diversified drivers — no single segment above ~40% revenue share unless it is a known group contract. Month OTB growing with positive net pickup in `whats_changed`.

**Concerning:** One segment (group event, OTA, single corporate) carries >50% of month revenue. Negative net pickup in the last 7 days while the month looked strong on paper — inventory may be eroding.

**Why it matters to a GM:** Drivers determine staffing, F&B planning, and which commercial relationships to protect. A month "driven by one group" has different operating risk than one driven by retail BAR.

## Heuristics

- Name the **top two revenue segments** and **top room-night segment** — if they differ, call out rate/mix.
- If MICE/group codes (CNI, CGR, EVEN, SMERF) dominate, flag group dependency for that month.
- Corporate macro_group share >35% in a leisure month may signal negotiated rate compression.
- Always state the month filter — "July OTB as of [as-of]" — so the GM knows the snapshot date.

## Trap

**Ranking by room nights when the GM cares about revenue** (or vice versa). Event/group segments often have fewer nights but large revenue per night, or the opposite for OTA retail. Read both `share_pct_nights` and `share_pct_revenue` from `segment_mix`.

## Recommendation levers

1. **Double down:** If retail BAR/FIT drives high-ADR share, protect rate on compression dates — do not discount into strength.
2. **Fill gap:** If month is underweight vs STLY and pace is soft, targeted promo on underperforming segment only — not hotel-wide.
3. **Protect anchor:** If one corporate or group account drives the month, confirm contract terms and attrition clauses with sales.

## Briefing scaffold

> **Headline:** [Month] is driven by [top segment(s)] — [X]% of revenue, [Y]% of nights.
> **Drivers:** [2–3 segments with shares; note revenue vs night divergence if any]
> **Risk:** [Concentration or negative recent pickup]
> **Action:** [Segment-specific lever — rate fence, group release, targeted promo]
