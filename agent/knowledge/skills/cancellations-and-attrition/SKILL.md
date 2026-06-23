---
name: cancellations-and-attrition
description: Use when assessing cancellation volume, lost revenue, or whether attrition is eroding forward OTB.
---

# Cancellations and attrition

## When to use

Load when the GM asks "how much did we lose to cancellations?", "what cancelled in June?", or whether attrition is eating forward business.

## Tools to call

- `cancellations(month="YYYY-MM")` — cancelled reservations, room nights, lost revenue by cancellation month.
- `cancellations()` — all-time cancelled volume if no month specified.
- `whats_changed(days=7)` — recent forward cancellations vs new bookings (net effect).
- `revenue_on_books(group_by="month")` — scale lost revenue vs remaining OTB for affected stay months.

## Comparison baselines

- **Cancellation period vs stay period:** `cancellations` filters on **cancellation_datetime**, not stay_date — a June cancel may affect July stays.
- **Lost revenue vs OTB:** Lost revenue from cancels in a month vs OTB revenue for forward stays — attrition rate context.
- **Net pickup:** `whats_changed` cancelled nights vs new nights — operational attrition trend.
- **Historical norm:** 24 cancelled reservations in full dataset (`describe_dataset`) — compare monthly cancel count to total book size (~250 reservations).

## Interpretation

**Healthy:** Cancellation volume stable; net pickup positive in `whats_changed`; lost revenue small relative to OTB for affected stay months.

**Concerning:** Spike in `cancellations` for a month; negative net room nights in `whats_changed`; lost revenue concentrated in a peak stay month — inventory hole forming.

**Why it matters to a GM:** Cancellations are immediate revenue risk and a leading indicator of group attrition, corporate travel pullback, or rate/booking friction. Forward cancellations are more urgent than historical ones.

## Heuristics

- Always state whether you mean **cancellation month** or **stay month** — the tool uses cancellation date.
- Quote all three: cancelled reservations, room nights, lost revenue — reservations understate multi-room cancels.
- If `whats_changed` shows high cancelled nights but low `cancellations(month=current)`, cancels may be spread across months or coded on forward stays — cross-check.
- Group blocks: large single cancel often one reservation with many nights — flag to sales, not just RM.

## Trap

**Using stay-date filters to count cancellations** or mixing cancelled rows into OTB totals. Cancelled business belongs in `cancellations` and the cancellation side of `whats_changed`, not `revenue_on_books`.

## Recommendation levers

1. **Group attrition:** Contact account owner on large cancelled blocks; review cut-off and attrition clause dates.
2. **Deposit tightening:** If FIT/OTA cancels spike, enforce prepay or shorter free-cancel window on promo rates.
3. **Re-fill priority:** For peak stay dates hit by cancels, yield to BAR/retail before OTA discount — protect rate on replacement business.

## Briefing scaffold

> **Headline:** [N] cancellations in [period] — [X] room nights, $[Y] lost revenue.
> **Drivers:** [Net pickup context; concentration in stay months]
> **Risk:** [Peak month hole / negative net week / group attrition]
> **Action:** [Sales follow-up / deposit policy / refill yield strategy]
