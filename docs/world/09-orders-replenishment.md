# Document 9 — Orders / Replenishment

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 10 (Promotions & Events) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: where Document 8's `Deliveries[t]` actually comes from — the ordering policy that decides when and how much a store orders, the two-stage structure (stable policy parameters vs. day-specific order events) mirroring Document 6's demand model, the genuine business variability Document 1 already committed this document to, and why the order record itself needs no Latent/Observable split — an even stronger case than Document 7's conclusion about Sales.

Does **not** define: promotional pre-stocking mechanics (Document 10, though this document leaves room for it); the inferred-ordering-pattern algorithm the Decision Platform will eventually run (Analytical Engine milestone); a distribution-center/warehouse layer (flagged as a simplification, not designed); Observed orders as a Phase 2 feed (M2B, though Document 1 already confirmed this feed gets no artificial fault injection).

## Closing the loop

Document 8 left `Deliveries[t]` as an acknowledged external input, owned by this document. This is where the loop the user has been tracking since Document 8 actually closes:

```text
Physical Inventory[t]
        ↓  (low stock, per this store-SKU's ordering policy)
Order placed[t]
        ↓  (lead time — this document's job)
Delivery arrives[t + lead time]
        ↓
Physical Inventory[t + lead time + 1]
        ↓
        └──── feeds back into the next cycle's ordering decision
```

Nothing here is circular: an order at time `t` depends only on `physical_inventory[t]` (already generated, by Document 8) and this store-SKU's exogenous policy parameters — never on inventory, sales, or demand at any time later than `t`. See [The acyclicity rule: no lookahead](#the-acyclicity-rule-no-lookahead) below.

## Granularity and party

**Proposed:** orders are generated and tracked at store-SKU-day granularity, consistent with everything since Document 6. This sharpens, rather than contradicts, Document 1's retailer-level language ("Orders = replenishment orders the retailer places to NovaFoods") — the retailer is the commercial counterparty and customer of record, but the thing that actually needs replenishing is a specific store's shelf, so the operational unit of an order is store-SKU, the same way `physical_inventory` is.

## Confirmed simplification: no distribution-center layer

**Confirmed: skip it, for the initial model.** A real retailer's actual distribution chain often looks like:

```text
Store
  ↓
Retailer DC
  ↓
Retailer procurement
  ↓
NovaFoods
```

— potentially with several DCs, regional inventory pools, and inter-DC transfers. Modeling that properly would mean an entirely second inventory-and-replenishment system (DC inventory, NovaFoods-to-DC lead times, DC allocation logic, DC-to-store replenishment) sitting on top of the one this document already defines. For the initial vertical slice, the model stays:

```text
Store
  ↓
Order
  ↓
Lead time
  ↓
Delivery
  ↓
Store inventory
```

**Documented explicitly as a simplification, not a claim that direct-to-store shipment is universally representative of real CPG distribution.** A retailer DC layer is a plausible future extension that can be added later without changing the fundamental architecture — it would insert a stage, not redesign the causal chain this document establishes.

## The two-stage structure, mirroring Document 6

**Proposed**, following the same shape Document 6 used for demand, for the same reason — separating a relatively stable structural layer from day-specific realized events:

```text
Ordering policy (structural, relatively stable per store-SKU)
    review cadence · order-up-to level · lead time
        ↓
Actual order events (day-specific, with genuine business variability)
```

**Ordering policy** is proposed to include: a review cadence (how often this store-SKU is evaluated for reorder — not necessarily daily), a target/order-up-to level, and a lead time (the delay between order and delivery). **Actual order events** are what a specific review cycle actually produces, incorporating the variability below.

## Order triggering and sizing — qualitative principles, not a formula

**Confirmed: periodic-review, order-up-to-level**, chosen over a continuous reorder-point model (an order triggered the instant stock crosses a threshold, independent of any review schedule). On its review day, a store-SKU orders enough to bring `physical_inventory` back up to a target level. That target is plausibly a function of expected demand over the review cycle plus lead time, plus a safety buffer, itself informed by `store_scale_class` (Document 4) — larger/higher-scale stores need proportionally larger buffers. As with every generative formula in this series (Document 4's demand mapping, Document 6's modifiers, Document 7's capping), **only the qualitative shape is proposed here; exact target-level formulas, review cadences, and lead-time distributions are implementation decisions**, not planning-document decisions.

**Why the policy/event split matters here specifically:** the policy gives structure; actual orders must not be mechanically determined by it. Two stores with similar `store_scale_class` and the same review cadence shouldn't place identical orders on identical days:

```text
Store A                    Store B
Mon → 120 units            Tue → 75 units
Wed →   0 units            Thu → 110 units
Fri →  90 units
```

This is the exact same discipline as Document 6's Potential-Demand-vs-Actual-Demand split, applied to orders: `Policy → expected behaviour → actual order`, with legitimate variability at the last step — not `Every Tuesday: order = exactly X`, which would make the ordering pattern trivially recoverable the same way a deterministic `store_scale_class → demand` mapping would have.

## Genuine business variability

Document 1 already confirmed this document inherits a specific list of real phenomena — business reality (Phase 1), not data error (Phase 2) — and this section is where that commitment is kept:

- **Irregular orders** — a store orders off its normal cycle.
- **Changing order cadence** — a store's ordering frequency drifts over time.
- **Promotional orders — confirmed, named explicitly as a Phase 1 phenomenon, not just structurally accommodated:**

  ```text
  Normal demand expectations
            +
  Promotional event (known ahead of time, Document 10)
            ↓
  Changed replenishment requirement
            ↓
  Potential pre-stocking
            ↓
  Larger/earlier order
  ```

  Naming this now matters for a specific reason: without it, a large order placed just before a promotion could later be mistaken by an analytical model for anomalous ordering behavior, when it's actually perfectly rational given the store knew the promotion was coming. So the division of labor is explicit: **this document establishes that orders can respond to promotional expectations**; **Document 10 defines what a promotion actually is and its demand/order effects.** No promotional mechanics are designed here.

- **Unusually large orders** — e.g., holiday stock-up.
- **Stores changing behavior over time** — a store's typical pattern shifts, not just noise around a fixed policy.
- **New stores with little history — confirmed, and not from `store_scale_class` alone.** A newly-assorted store-SKU pair (Document 5's `effective_from`) has no order history to base a policy on, so its "initial stocking" event (deferred here by Document 8) has to be bootstrapped from *pre-opening expectations*, not a single attribute:

  ```text
  New store
     │
     ├── store_scale_class
     ├── physical assortment
     ├── SKU characteristics
     └── expected demand profile
               ↓
        Initial inventory/order target
  ```

  `store_scale_class` is one input among several — combined with the store's actual planned assortment and SKU-level characteristics to form an expected-demand-profile estimate, itself carrying stochastic variation (a Scale-4 store's initial target is not exactly 4× a Scale-1 store's, consistent with this project's standing rejection of deterministic scale-to-outcome mappings). **Critically: bootstrap quantities are initialized from structural, pre-opening information only — never from future realized sales.** A new store's first order must be generatable from what's knowable *before* it opens, or the no-lookahead rule below would be silently violated at the one moment it's easiest to forget.

All of this is **Phase 1 business reality**, generated deliberately, not left to arbitrary noise — consistent with the project's standing preference for simulated causes over randomness.

## The acyclicity rule: no lookahead

Extends Document 6's generalized rule with a temporal-specific reinforcement, since Orders is the first document where "don't read downstream output" and "don't peek at the future" become genuinely different failure modes worth naming separately, and where getting it wrong would be easiest — generating a full historical world naturally puts "the future" within arm's reach of the generator at every step. Made concrete: when generating an order on, say, January 10:

```text
CAN use:
  - inventory available on Jan 10
  - known assortment as of Jan 10
  - known promotion schedule (if already determined — Document 10)
  - historical information available by Jan 10
  - this store-SKU's replenishment policy

CANNOT use:
  - Jan 11 demand
  - Jan 11 sales
  - future inventory
  - future orders
```

**Prominent, standing invariant**, not a one-off caution: without it, the simulator could accidentally construct a retailer with perfect knowledge of the future, producing ordering behavior that's unrealistic precisely because it's *too* good — and that failure mode wouldn't necessarily be obvious just from looking at the output. No lookahead applies even indirectly through a derived feature, mirroring the exact discipline Document 6 established for the derived-feature loophole.

## Order record reliability — no split needed, a stronger case than Sales

Document 7 concluded Sales doesn't need a Latent/Observable/Inference split because a perfect Phase 2 feed would just report the truth. **Orders make an even stronger version of that same argument, already stated as a confirmed decision back in Document 1**: NovaFoods isn't receiving a *report* of an order at all — it *is* the order's other party. There's no feed to degrade in the first place for the order record itself; Document 1 already confirmed no artificial Phase 2 fault injection applies to it, specifically to avoid "unnecessarily weakening one of the strongest signals in the system." Nothing in this document changes that — it's carried forward, not re-argued.

## What's *not* reliable: the inferred pattern

**The one thing that stays genuinely uncertain**, also already flagged in Document 1: a specific order event is a hard fact, but *"this store-SKU's normal cadence is every two weeks, roughly 20 units"* is an inferred pattern, not a fact — something the Decision Platform would have to learn from historical order records, the same way it has to learn `store_scale_class` from indirect signals. Nothing about that inference is designed here; it belongs to the Analytical Engine milestone. This document only needs to generate real order events with real variability for that future inference problem to actually be non-trivial.

## Illustrative example (not a real mechanism)

Purely to make the loop concrete — none of this is a real decision:

```text
BayMart Store #118 × RidgeCrest Kettle-Style Sea Salt Chips, 8 oz, US

Ordering policy: review every 14 days, order-up-to 150 units, lead time 5 days

Day 20 (review day): physical_inventory = 35
        ↓
Order placed: 150 − 35 = 115 units
        ↓
Day 25 (5-day lead time later): Delivery = 115 units
        ↓
physical_inventory[26] = physical_inventory[25] − Sales[25] + 115
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Retailer DC layer | Defer — documented simplification, not a claim direct-to-store is universal |
| Initial logistics model | NovaFoods → Store, directly |
| Replenishment policy | Periodic review + order-up-to-level, not continuous reorder-point |
| Policy vs. actual events | Confirmed — actual orders must not be mechanically determined by policy (two similar stores order differently) |
| New-store bootstrap | Structural characteristics (`store_scale_class` + planned assortment + SKU characteristics) + expected-demand-profile estimate + stochastic variation — not `store_scale_class` alone |
| Bootstrap from future realized sales? | Absolutely not — pre-opening information only |
| Promotional pre-stocking | Confirmed named explicitly as a Phase 1 phenomenon now; mechanics remain Document 10's job |
| Order record Latent/Observable split? | No — confirmed, stronger case than Sales |
| No-lookahead | Confirmed as a prominent, standing invariant, not a one-off caution |

## Explicitly out of scope for this document

**Document 10:** promotional pre-stocking mechanics — magnitude, timing relative to the promotion.

**M2B / Phase 2:** orders as an actual feed — though per Document 1, this feed gets no artificial fault injection, unlike most others.

**Analytical Engine milestone:** the inferred-ordering-pattern algorithm.

**Deferred, not scoped:** a distribution-center/warehouse layer between NovaFoods and stores.
