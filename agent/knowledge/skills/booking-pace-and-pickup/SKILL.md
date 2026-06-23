---
name: booking-pace-and-pickup
description: Use when judging whether forward OTB is building fast enough or stalling based on recent booking activity.
---

# Booking pace and pickup

## When to use

Load when the GM asks "how's pickup?", "are we booking fast enough?", "what came in this week?", or whether forward inventory is accelerating or stalling.

## Tools to call

- `booking_pace(days=30)` — daily booking volume on create date for forward stays.
- `whats_changed(days=7)` — net change from new bookings minus cancellations (default 7; extend to 14 if GM asks "fortnight").
- `revenue_on_books(group_by="month")` — current OTB level to contextualize pace.
- Optional: `stly_comparison` — is OTB ahead/behind while pace is slow (burning lead)?

## Comparison baselines

- **Last 7 vs prior 7 days:** Compare `whats_changed(days=7)` to a second call with `days=14` and infer the earlier week — acceleration or deceleration.
- **Pace curve:** `booking_pace` daily series — lumpy group bookings vs steady retail.
- **OTB level:** High OTB with weak pace = relying on existing book; low OTB with strong pace = catching up.
- **STLY gap:** Strong pace but still behind STLY = need sustained run rate, not one good week.
- **Seasonality:** Forward stays only — pace never includes past stays (tool filters `stay_date >= as_of`).

## Interpretation

**Healthy:** Positive net room nights in `whats_changed`; `booking_pace` shows consistent daily pickup; OTB trending toward or above STLY.

**Concerning:** Net negative week (cancellations exceed new bookings on forward stays). Pace flat or declining while OTB trails STLY — the hotel is falling behind the booking curve.

**Why it matters to a GM:** Pace tells you whether to hold rate or stimulate demand. Slow pace with good OTB still means future weeks may hollow out as cancellation windows open.

## Heuristics

- Quote **net room nights** from `whats_changed`, not gross bookings alone — cancellations are part of pace.
- A single large group booking can spike one day on `booking_pace`; note it as lumpy, not "surging demand."
- If new revenue is strong but net nights flat, check ADR/mix — may be upsell, not volume.
- "Last 7 days" always means booking/cancellation **activity dates**, not stay dates — say so explicitly once.

## Trap

**Confusing booking pace with OTB inventory.** Pace is what **arrived** recently; OTB is what **is held** for the future. Strong OTB + zero pace = full but not growing; strong pace + weak OTB = early in the build.

## Recommendation levers

1. **Hold rate:** Positive net pickup and OTB ahead of STLY — resist discounting; test min stay on peak nights.
2. **Stimulate selectively:** Negative net pickup on key months — segment-targeted promo (FIT/BAR), not OTA blanket discount.
3. **Cancellation hygiene:** Rising cancelled nights in `whats_changed` — review deposit policy and follow up tentative group blocks.

## Briefing scaffold

> **Headline:** Pickup over the last [N] days is [net +/- X room nights] — [accelerating / stalling / eroding].
> **Drivers:** [New bookings vs cancellations; pace pattern — steady vs lumpy]
> **Risk:** [OTB vs STLY gap if pace doesn't sustain]
> **Action:** [Hold / stimulate / attrition follow-up]
