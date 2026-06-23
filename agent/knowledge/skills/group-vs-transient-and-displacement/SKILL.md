---
name: group-vs-transient-and-displacement
description: Use when weighing group block share against transient retail and displacement risk on peak dates.
---

# Group vs transient and displacement

## When to use

Load when the GM asks "how much is group?", "are we too group-heavy?", or whether blocks are displacing higher-rated transient business.

## Tools to call

- `group_vs_transient(month="YYYY-MM")` — OTB split by `is_block` flag.
- `segment_mix(dimension="macro_group", month="YYYY-MM")` — MICE vs retail vs corporate rollup (different lens from is_block).
- `revenue_on_books(group_by="month", month="YYYY-MM")` — month OTB total for context.
- Optional: `adr_analysis` — transient retail ADR vs implied group rate if segments diverge.

## Comparison baselines

- **Group revenue share:** From `group_vs_transient` → `group.share_pct_revenue` vs `share_pct_nights`.
- **Month vs hotel total:** Group share in peak month vs full OTB — seasonal group dependency.
- **Macro_group cross-check:** MICE codes (CNI, CGR, EVEN, SMERF) vs `is_block` — they overlap but are not identical.
- **Transient retail ADR:** Executive and Standard King ADR from `adr_analysis` as displacement benchmark.

## Interpretation

**Healthy:** Balanced mix for the season — group fills shoulder or contracted peaks; transient retail holds compression dates. Group night share roughly aligned with revenue share.

**Concerning:** Group >50% revenue share in a peak month with flat transient pickup. Group revenue share below night share — low group rate. High group share while `whats_changed` shows weak retail pace — displacement may have already occurred.

**Why it matters to a GM:** Group blocks guarantee volume but cap rate. Accepting low group on sold-out nights turns away higher ADR transient — displacement cost often exceeds the group room revenue.

## Heuristics

- **Group = `is_block` true** — not the same as MICE macro_group (tool caveat). Say which definition you use.
- Displacement test: if group ADR (implied from revenue/nights) is >15% below retail BAR/ADR, flag on compression dates.
- Shoulder months: high group share is often good; peak months: same share is a strategic choice, not automatically good.
- Always mention **release dates** conceptually — group blocks should wash if transient demand materializes.

## Trap

**Using MICE macro_group or market codes as "group" when the question is block business.** CGR/EVEN may be group-like but `group_vs_transient` uses `is_block`. Mislabeling misstates displacement risk.

## Recommendation levers

1. **Minimum group rate:** Set floor at ~90% of forecast transient ADR for peak dates — walk away below that.
2. **Release strategy:** 30–60 day release on soft group blocks to recapture retail if pickup strengthens.
3. **Shoulder fill:** Push group into shoulder where displacement cost is zero; protect peak for BAR/FIT/OTA retail at rate.

## Briefing scaffold

> **Headline:** Group is [X]% of OTB revenue ([Y]% of nights) [for month if filtered].
> **Drivers:** [Block vs transient split; macro_group context]
> **Risk:** [Peak displacement / low group rate / weak retail alongside blocks]
> **Action:** [Rate floor / release / shoulder vs peak strategy]
