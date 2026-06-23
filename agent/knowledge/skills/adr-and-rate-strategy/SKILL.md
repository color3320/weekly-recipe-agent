---
name: adr-and-rate-strategy
description: Use when comparing room-type rate levels, premium positioning, or whether rate is helping/hurting mix.
---

# ADR and rate strategy

## When to use

Load when the GM asks "which room type leads on rate?", "are we pricing Executive correctly?", or whether ADR supports the revenue strategy.

## Tools to call

- `adr_analysis` — ADR by room type (KS, TB, EX) at reservation grain.
- `segment_mix(dimension="market_code", revenue_measure="room")` — room revenue mix by segment.
- `revenue_on_books(revenue_measure="room")` — total room revenue context.
- Optional: `stly_comparison` — nights vs revenue gap for rate vs volume diagnosis.

## Comparison baselines

- **Room type ladder:** EX vs KS vs TB ADR from `adr_analysis` — premium spread should reflect physical product (Executive > Standard King > Twin).
- **ADR vs segment mix:** High OTA/PROM share with strong headline ADR may still mean net dilution — check segment room revenue shares.
- **STLY revenue vs nights:** From `stly_comparison` — ADR implied gap without recalculating ADR yourself.
- **Capacity by type:** KS 52, TB 20, EX 26 rooms — ADR leadership on EX matters less if KS drives volume.

## Interpretation

**Healthy:** Clear premium on EX over KS/TB; ADR hierarchy matches product positioning; STLY ahead on revenue with stable or improving mix.

**Concerning:** Inverted or compressed spread (TB near EX) — rate shop or mapping error. Strong nights, weak revenue vs STLY — selling too cheap. Highest ADR type has tiny night share — premium product not in the sell mix.

**Why it matters to a GM:** ADR is the price lever — mis-set Executive premium leaves money on the table; over-discounted Standard King trains the market to wait for promo.

## Heuristics

- Quote the three ADR levels and **spread**: EX premium over KS in dollars and percent — GMs think in positioning, not isolated numbers.
- Do not recompute ADR from revenue ÷ nights — tool uses reservation-level `AVG(adr_room)` (see caveats).
- If recommending rate change, tie to **segment**: raise BAR not corporate contracted unless contract window allows.
- Room-only vs total revenue: packages inflate total — use `revenue_measure="room"` when discussing rate.

## Trap

**Stay-weighted ADR mental math** — averaging daily revenue/nights gives a different number than `adr_analysis`. Trust the tool; narrate the spread, do not derive ADR yourself.

## Recommendation levers

1. **Premium fence:** Widen EX vs KS spread if EX ADR premium <~25% — upsell and rate floor on Executive.
2. **BAR leadership:** If STLY behind on revenue, test +5% BAR on compression weeks before broad OTA cut.
3. **Mix shift:** If KS ADR strong but EX underbooked, package or upgrade path from Standard King — capture premium physically available.

## Briefing scaffold

> **Headline:** [Highest ADR type] leads at $[X]; EX premium over KS is [Y]%.
> **Drivers:** [Room type ladder; segment room revenue mix]
> **Risk:** [Compression / dilution / inverted spread]
> **Action:** [Premium fence / BAR test / upgrade path]
