---
name: concentration-and-key-account-risk
description: Use when evaluating revenue concentration in top companies or reliance on a few large multi-room bookings.
---

# Concentration and key-account risk

## When to use

Load when the GM asks "who are our biggest accounts?", "is revenue too concentrated?", or "do we rely on a few big bookings?"

## Tools to call

- `concentration(top_n=10, large_booking_rooms=5)` — top companies by OTB revenue, top-3 share, large multi-room booking count.
- `segment_mix(dimension="macro_group", filter_corporate=True)` — corporate macro_group slice if concentration is B2B-driven.
- Optional: `segment_mix(dimension="market_code")` — CSR/CNR corporate codes vs group MICE codes.

## Comparison baselines

- **Top-3 revenue share:** From `concentration` → `top3_revenue_share_pct` — single headline concentration metric.
- **Top company vs total OTB:** Largest company revenue / `total_otb_revenue` from same tool.
- **Large bookings:** Count of reservations with ≥5 rooms (`large_booking_count`) — operational and attrition risk.
- **Diversification norm:** No defensible industry law — use judgment: top-3 above ~50% revenue is elevated for a 98-room hotel.

## Interpretation

**Healthy:** Top-3 share moderate; revenue spread across several companies and segments; few mega-multi-room bookings unless expected group season.

**Concerning:** Top-3 share above ~50%. One company dominates top_companies list. Multiple large bookings (≥5 rooms) on same peak dates — one attrition event moves the month.

**Why it matters to a GM:** Concentration is credit and relationship risk — one lost account or cancelled block can miss budget. Operations also strains when one group fills the hotel.

## Heuristics

- Name the **top 2–3 companies** with revenue and room nights — GM recognizes names, not percentages alone.
- "(no company)" bucket in results is transient retail — high share there means concentration is segment, not account risk.
- Large booking threshold default 5 rooms — note if lowering to 3 changes the story (call tool with `large_booking_rooms=3`).
- Pair with `group_vs_transient` if concentration is group-driven.

## Trap

**Confusing company concentration with segment concentration.** Top CSR corporate account ≠ "corporate segment" total. `concentration` is by `company_name`; segment mix is by market/macro code. A diversified segment can still have one dominant account.

## Recommendation levers

1. **Key account plan:** Top 3 companies get dedicated sales touch and contract review before peak season.
2. **Attrition buffers:** On months dominated by one block, hold release dates and minimum group rate floors.
3. **Diversify fill:** If top-3 share high, prioritize new corporate or retail contracts for shoulder dates — do not add dependency on the same accounts.

## Briefing scaffold

> **Headline:** Top 3 accounts hold [X]% of OTB revenue — [concentrated / diversified].
> **Drivers:** [Named top companies; large booking count]
> **Risk:** [Single-account or single-block dependency]
> **Action:** [Account plan / attrition buffer / diversify fill]
