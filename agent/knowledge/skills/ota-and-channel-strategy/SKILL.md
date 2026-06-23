---
name: ota-and-channel-strategy
description: Use when judging OTA/channel mix, direct-booking dependency, or commission-driven margin risk.
---

# OTA and channel strategy

## When to use

Load when the GM asks "are we too dependent on OTA?", "how's our direct mix?", or whether commission channels are eroding margin.

## Tools to call

- `ota_dependency` — OTA market share of OTB nights and revenue.
- `segment_mix(dimension="market_code")` — OTA vs other segments; rank by nights and revenue.
- `segment_mix(dimension="channel_code")` — booking path: WEB (digital) vs REC (direct) vs EMA/WAL.
- `whats_changed(days=7)` — recent OTA vs total pickup (infer from segment if needed via market filter context).
- Optional: `stly_comparison` + `segment_mix` — is OTA share growing vs STLY position?

## Comparison baselines

- **Night share vs revenue share:** From `ota_dependency` — `ota_share_pct_nights` vs `ota_share_pct_revenue`. Aligned = proportional; revenue share higher = cheaper OTA ADR; revenue share lower = OTA buying upmarket (still commission-heavy).
- **OTA vs total retail:** OTA is one market code; BAR, PROM, FIT are retail alternatives — compare combined retail mix.
- **Channel path:** `channel_code` WEB vs REC — dependency is also a **direct booking** question, not only OTA market label.
- **Tool threshold:** `ota_dependency` caveats flag revenue share above ~30% as elevated dependency.
- **Recent trend:** `whats_changed` — is digital volume accelerating while REC is flat?

## Interpretation

**Healthy:** OTA night and revenue shares roughly aligned; REC (direct) holds meaningful share; OTA is one of several top segments, not the dominant revenue driver.

**Concerning:** OTA revenue share > night share (rate dilution plus commission). Revenue share above ~30%. WEB growing, REC flat — paying commission for business you could shift direct. OTA accelerating in `whats_changed` while total pace is weak — becoming the default fill channel.

**Why it matters to a GM:** OTA is margin, not just volume — typically 15–25% commission on top of often-discounted BAR. Over-reliance compresses GOP and weakens rate integrity on compression dates.

## Heuristics

- Never answer OTA dependency with **night share alone** — always pair with revenue share from `ota_dependency`.
- ~15–20% OTA night share can still be fine if revenue share is lower and direct is growing; ~25%+ revenue share warrants action regardless of nights.
- Rate parity: direct should be within ~5% of OTA landed rate — if REC share is low, parity or promo failure is the first suspect.
- OTA market code ≠ WEB channel — corporate can book WEB; OTA segment can flow through multiple channels. Use both tools.
- For WEB vs OTA split, use `ota_dependency` fields **`ota_market_on_web_channel_room_nights`** and **`non_ota_on_web_channel_room_nights`** — never reuse `ota_room_nights` as "OTA on WEB" (that total includes walk-in and other channels).
- Quote exact figures from envelopes in tables; do not round tool dollars or counts.

## Trap

**Equating `market_code = OTA` with `channel_code = WEB`.** Market is segment economics (who pays what rate); channel is booking path (who took the reservation). A hotel can have moderate OTA market share but high WEB channel share from non-OTA segments, or the reverse. Judge dependency with both dimensions.

**Substituting `ota_room_nights` into a WEB-channel sentence.** Example failure: "104 WEB nights, 71 are OTA" when `ota_room_nights` = 71 (all channels) but `ota_market_on_web_channel_room_nights` = 69 and `non_ota_on_web_channel_room_nights` = 35. State each number with its correct label.

## Recommendation levers

1. **Parity audit:** Compare BAR/REC published rate to OTA landed rate for next 30 days of stay — fix inversions before cutting OTA.
2. **Direct fence:** Member or direct-only promo on REC for retail dates where group blocks are not binding — shift share without hotel-wide discount.
3. **Selective OTA cap:** Reduce OTA allocation on peak compression nights rather than global OTA cuts — protects rate where displacement cost is highest.

## Briefing scaffold

> **Headline:** OTA is [X]% of OTB nights and [Y]% of revenue — [dependency assessment].
> **Drivers:** [Rank vs EVEN/CGR/other; WEB vs REC channel split]
> **Risk:** [Revenue > night share; >30% revenue; accelerating OTA with flat direct]
> **Action:** [Parity audit / direct fence / selective cap]
