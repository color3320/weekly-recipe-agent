---
name: revenue-manager-briefing-style
description: Use when formatting any substantive GM answer — turns tool output into BLUF, drivers, risk, and action without adding new numbers.
---

# Revenue manager briefing style

## When to use

Load this skill whenever the answer is more than a single number — anything the GM would discuss in a morning stand-up.

## Tools to call

None for formatting. Use numbers already returned by Part 5 tools. Do not fetch new data unless a beat is missing a critical figure. Use `segment_name` on segment rows or `label_maps` from `describe_dataset` to label codes.

## Comparison baselines

Structure beats the metrics:

| Beat | Purpose | GM test |
|------|---------|---------|
| **BLUF** | 1–2 sentences — direct answer to the question | Would they repeat this to the owner? |
| **Supporting detail** | 2–3 quantified explanations below the summary | Can they see where the number comes from? |
| **Caveat** | Plain-English qualification if needed | Is the limitation clear without jargon? |
| **Risk** | Forward-looking downside | What keeps them up at night? |
| **Action** | Concrete levers | Can they assign someone today? |

## Interpretation

**Healthy briefing:** Opens with BLUF — judgment that directly answers the question — then supports with numbers, ends with a decision. Reads like a person, not a dashboard export.

**Weak briefing:** Opens with a table before answering, lists segments alphabetically by bare code, ends with "monitor the situation." Accurate but useless.

## Heuristics

- BLUF ≤ 40 words (1–2 sentences). It must contain the answer before any table.
- Supporting detail: max three bullets; each uses full segment/channel names.
- Never expose SQL, table names, tool names, grain, or raw status values to the GM.
- Risk: one primary risk, not a laundry list. Secondary risks get one clause.
- Action: verbs first — "Fence BAR on direct web," "Release group block on Aug 12," "Audit OTA parity for September."
- **Exact figures in tables:** Use tool `key_numbers` verbatim (room nights, reservations, revenue, share_pct). Do not round $33,674 to $33,700 or 10.9% to 11% in a breakdown table.
- Round for speech only in a casual one-liner when no table follows — e.g. "$102.6k OTB revenue" — never round figures the GM will reconcile against a table.
- **Currency:** USD ($) only — never mix $ and £ in the same briefing.
- **Segment labels:** Always full lookup name with code optional in parentheses — e.g. "Conference / Incentive Group (CNI)". Never bare codes (`CNI`, `WEB`, `KS`). If only a code appears (e.g. from a custom query), map via `label_maps` before answering.

## Trap

**Dashboard recitation:** repeating envelope headlines and every row without saying what it means commercially. The tools already gave accuracy; your job is judgment.

## Recommendation levers

When stuck:

1. Write the BLUF as if the GM has 10 seconds — answer the question first.
2. Ask "compared to what?" for drivers — STLY, last 7 days, typical mix, capacity.
3. Ask "what if this continues?" for risk.
4. Ask "what would I do Monday morning?" for action.

## Briefing scaffold

```
**BLUF:** [1–2 sentences that directly answer the question with the key number or judgment]

**Supporting detail:**
- [Quantified driver 1 — full segment/channel name]
- [Quantified driver 2]

**Caveat:** [Plain-English qualification if needed — no database jargon]

**Risk:** [One forward-looking concern and why it matters to margin, occupancy, or concentration]

**Action:**
1. [Concrete lever]
2. [Concrete lever]
```

Skip sections that genuinely do not apply, but never skip BLUF and Action on a strategic question. Never place a table above the BLUF.
