# Document 11 — Commercial Activity

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. This completes the initial Ground Truth design (Documents 1–11); a full consistency audit follows before any implementation begins.

## What this document defines (and what it doesn't)

Defines: the commercial agent as a human participant in the business process, not a data feed — store visits (policy vs. actual events, mirroring Document 6's demand and Document 9's ordering structure), the observations and actions a visit can produce, retailer-level interactions, and why none of this becomes Ground Truth by virtue of being recorded. Also disambiguates this document's "feedback/intervention" from the unrelated, later concept of recommendation feedback.

Does **not** define: the agent-observation fidelity/noise model — how accurate, biased, or systematic an agent's stated observation is relative to reality (flagged as an architectural question this document surfaces but doesn't resolve — see below); recommendation feedback (the M7 Human Feedback Loop concept — a different thing entirely, addressed explicitly below to prevent confusion); a general CRM-style account-management model.

## The central risk: a human observation is a fourth observable channel, never Ground Truth

Stated first, because this document is the one place in the series where it would be easiest to get backwards: **an agent's statement about what they saw must never be written into Phase 1 state.** If an agent visits a store and reports "this product appears to be out of stock," that is a human observation — not `physical_inventory = 0`. The physical state remains whatever Document 8 already generated, independently; the agent's statement is a new, additional, imperfect signal about it, sitting in exactly the same tier as POS and retailer-reported data, not a shortcut into Phase 1 truth:

```text
Physical reality (Phase 1, latent)
        │
   ┌────┼──────────────────┐
   ↓    ↓                  ↓
  POS  Retailer          Human
       reports          observations
   └────┼──────────────────┘
        ↓
     Inference
```

This isn't a new architectural idea — Document 1 already placed "commercial feedback (from agent store visits — anecdotal, non-systematic)" in the Observable tier on day one. This document is where that placement finally gets designed rather than just named.

## Where human observation sits, architecturally — confirmed as a separate future concern, not M2B

**Confirmed: do not fold this into M2B.** M2B is specifically the simulation of *retailer-provided* observations; a commercial agent is NovaFoods' own employee, physically perceiving the store directly, not a retailer feed being degraded. Its imperfections are a different shape entirely: perception error, subjectivity, incomplete coverage (an agent sees part of a store, not all of it), recall/reporting lag, and sampling bias (which stores get visited, and how often).

```text
                    LATENT REALITY
                         │
             ┌───────────┴───────────┐
             ↓                       ↓
    Retailer system              Human agent
      observations               observations
             │                       │
             ↓                       ↓
          Phase 2               Commercial signal
             │                       │
             └───────────┬───────────┘
                         ↓
                     Inference
```

**Confirmed: no architectural commitment made now** about whether agent-observation fidelity eventually becomes its own phase/component or attaches somewhere else — that decision is deferred to whenever it's actually needed, not forced prematurely just because this document needs a placeholder. This document defines what an agent visit *is* and what it can produce; it deliberately does not design how faithfully that production represents reality.

## Structure: three branches, kept deliberately narrow

```text
Commercial Activity
       │
       ├── Store visit
       │      ├── observations
       │      ├── actions
       │      └── purpose tags
       │
       ├── Retailer interaction
       │
       └── Feedback / intervention
```

**Governing principle for all three:** this document exists because commercial activity produces useful business observations and interventions — not because a CPG company has meetings and sales calls that deserve modeling for their own sake. Every branch below is scoped to what feeds the observation/intervention chain, deliberately not a general CRM model (contact logs, meeting cadences, relationship-health scoring, and similar are out of scope entirely).

## Store visits: policy vs. actual, mirroring Demand and Orders

**Proposed**, following the same two-stage shape already used twice in this series:

```text
Visit policy (structural, relatively stable per store)
    visit cadence, informed by store_scale_class
        ↓
Actual visit events (day-specific, with genuine variability)
    routine visits, plus irregular/unplanned visits triggered by an issue
```

Higher-`store_scale_class` stores plausibly warrant more frequent coverage — a qualitative principle only, exact cadence formulas left to implementation, consistent with every other generative decision in this series. Actual visits are not mechanically determined by the policy, the same reason Document 9's actual orders weren't mechanically determined by the ordering policy: an unplanned visit (responding to a known issue) is itself a realistic, valuable phenomenon, not noise to eliminate.

## Purpose tags — multiple per visit, kept business-oriented and simple

**Confirmed: a visit carries a *set* of purpose tags, not one.** This is a restatement, not a new decision — Document 1 already confirmed "commercial visits are one event type carrying multiple purpose tags," and this document just applies it. A single stop can genuinely be an inventory check *and* an order follow-up, or a promotion check *and* routine coverage — modeling purpose as a single-select field would misrepresent a normal visit.

Proposed tag set — same treatment as every other classification list in this series (Retailer Type, Store Format, Promotion Type), a working starting set kept deliberately small rather than expanded speculatively:

```text
Store visit
├── assortment_check
├── inventory_check
├── promotion_check
├── retailer_relationship
├── issue_resolution
├── new_store_onboarding
└── order_follow_up
```

## Observations: a new observable channel for four already-established variables

**Proposed:** an agent's observations during a visit are a *new way of imperfectly seeing* quantities this series has already defined — not new latent variables. Explicitly:

- **`physical_assortment`** (Document 5) — "this SKU isn't on the shelf."
- **`physical_inventory`** (Document 8) — "this product appears to be out of stock" / "stock looks low."
- **Promotion `execution_state`** (Document 10) — "the promotional display is up" / "the promotion isn't running here."
- **Store classification** (Document 4's universalization problem) — an agent's general impression of a store (traffic, condition) is a plausible additional input to the eventual cross-retailer classification effort, alongside retailer-reported tiers.

Every one of these is stated as a human judgment about the corresponding Phase 1 quantity — never assumed accurate, never written back into the quantity itself. This document adds no new hidden state; it adds a new lens on state that already exists. Concretely, the rule this rules out:

```text
Agent says: "SKU appears to be missing from shelf"
        ↓
Correct:   another noisy signal about physical_inventory / physical_assortment
Wrong:     a new latent variable, e.g. "agent_believed_inventory"
```

The agent is a lens on existing reality, never a second reality.

## Actions: agents can causally affect Phase 1 state, within narrow bounds

**Confirmed: included now, not deferred.** An agent is a real participant in the business, not merely a sensor — a commercial representative visiting a store can change the state of the business, and modeling agents as passive observers only would be less realistic, not more conservative.

**The strong rule that makes this safe: an intervention must flow through an existing causal pathway, never create a new one.**

```text
Correct:
Agent → field intervention → Order (Document 9) → Delivery → Physical inventory

Wrong:
Agent → magically increases inventory
```

Two concrete instances, both routed through mechanisms already fully defined elsewhere: an agent personally restocking shelf-visible product from a backroom is a narrow, legitimate adjustment to `physical_inventory` (Document 8) — not a new inventory mechanism; an agent triggering an out-of-cycle replenishment order is an instance of Document 9's already-established "irregular orders" business variability — not a new order pathway. **Kept deliberately narrow and qualitative** — this document doesn't enumerate every possible intervention or design new mechanics; it establishes that visit-triggered adjustments to already-established state are legitimate, provided they're expressed through the same variables and rules those documents already defined, never a shortcut around them.

## Retailer interaction — minimal, explicitly not a CRM

**Proposed:** retailer-level (not store-level) commercial contact — a meeting, call, or negotiation with a retailer's buyer or category manager, distinct from any specific store visit. Minimal structure only: that an interaction occurred, with which retailer, and roughly why (e.g., trade-term negotiation, new-product presentation, relationship maintenance). No contact logs, no meeting notes, no attendee lists, no relationship-health metrics — anything resembling a full account-management system is explicitly excluded, per the governing principle above.

## Feedback / intervention — not the same thing as recommendation feedback

**Important disambiguation, since the name collides with an already-established, unrelated concept.** `docs/DATA_MODEL.md` and the project's Human Feedback Loop milestone (M7) already define "Feedback" as a commercial agent's response to a *Decision Platform recommendation* (confirmed / rejected / already resolved / wrong data / etc.). **That concept does not exist in Phase 1 at all** — Phase 1 has no notion of a Decision Platform, an analytical model, or a recommendation; it doesn't know it's being observed, let alone acted on by a downstream system.

This document's "feedback/intervention" is a different, earlier, purely Phase 1 phenomenon: an agent encountering a real-world business situation during a visit or interaction and reacting to it directly — flagging a concern to the retailer, escalating an issue, making a judgment call — independent of any recommendation system. Proposed name change to avoid the collision outright: **`field intervention`**, not "feedback," reserving "feedback" exclusively for the M7 concept it already names.

## The acyclicity / no-lookahead rule, reaffirmed

No different in kind from Documents 6, 9, and 10: a visit, observation, or action generated for day `t` may depend on Phase 1 state as of day `t` and this store's exogenous visit policy, never on anything later than `t` — an agent cannot visit today already knowing about a stockout that won't begin until next week.

## Illustrative example (not a real mechanism)

Purely to make the structure concrete — none of this is a real decision:

```text
BayMart Store #118, visited by Agent #204
  purpose tags: {inventory_check, promotion_check}

Observation: "RidgeCrest 8oz chips look low on shelf"
  (a human judgment — physical_inventory itself, independently generated
  by Document 8, might be 3 units or 30; this statement doesn't set it)

Action: agent requests an out-of-cycle order
  → Order (Document 9) → Delivery → Physical inventory
  (a legitimate instance of Document 9's "irregular orders" variability —
  not a new causal pathway)

Field intervention: agent flags a recurring display issue to the retailer
  contact — a real Phase 1 event, unrelated to any recommendation system
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Agent-observation fidelity model | Separate future concern — not folded into M2B; no architectural commitment made about where it eventually lives |
| Agent observations | Confirmed as an Observable-tier signal, same tier as POS/retailer reports |
| Agent actions | Included now, not deferred — an agent is a real business participant, not just a sensor |
| New causal pathways for actions | None — every intervention must flow through an existing mechanism (Document 8's inventory, Document 9's irregular orders) |
| Purpose tags per visit | Multiple, confirmed — restates Document 1's "one event type, multiple purpose tags" |
| Purpose taxonomy | Kept small and business-oriented, not expanded |
| `field intervention` naming | Kept — reserves "feedback" exclusively for the M7 recommendation-response concept |

## Explicitly out of scope for this document

**A separate future concern, deliberately not M2B:** the actual fidelity/noise model for agent observations — no architectural home decided here.

**M7 (Human Feedback Loop):** recommendation feedback — a distinct, later concept, explicitly not what this document's "field intervention" means.

**Implementation:** exact visit cadence formulas, action-triggering probabilities.

**Out of scope entirely, not deferred:** a general CRM/account-management model.
