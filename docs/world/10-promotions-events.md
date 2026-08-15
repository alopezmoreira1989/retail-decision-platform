# Document 10 — Promotions & Events

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 11 (Commercial Activity) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: the Promotion entity and its scope, the origin distinction that determines what NovaFoods knows about a promotion ahead of time, the planned-terms-vs-actual-execution gap this introduces, and exactly two causal effects — filling the demand-modifier slot Document 6 reserved and the pre-stocking slot Document 9 reserved. Events are folded into the same entity as a promotion type without a price component, not a separate concept.

Does **not** define: retailer-reported promotion execution as a Phase 2 feed (M2B); continuous non-promotional retail shelf pricing (out of scope entirely, not just deferred — see below); the demand-lift or pre-stocking formulas (implementation, consistent with every prior document's generative-formula discipline); any inference about whether a promotion happened (Analytical Engine milestone).

## The central risk: a promotion is a scheduled cause, never a post-hoc explanation

Stated first, because it's the specific trap this document exists to avoid: **it would be very easy to let "there was probably a promotion" become the simulator's convenient explanation for whatever demand or sales number it happened to generate.** That would be exactly backwards. A promotion has to be decided as part of the exogenous world — scheduled ahead of the dates it affects, the same way a store's `open_date` or a product's `active_from` is a fact fixed before the simulation runs through those days — and then it *causes* effects on demand and orders. It is never fitted after the fact to rationalize an anomaly, and it never gets invoked reactively while the day-by-day generation is running. This is the acyclicity/no-lookahead discipline from Documents 6 and 9, applied to a new entity that's specifically at risk of violating it, because "just add a promotion" is such a tempting shortcut when a generated number looks odd.

## What this document actually adds: two reserved slots, not a new causal web

Worth clarifying against the four-arrow sketch this document was scoped with (Promotion → demand, sales, inventory depletion, orders). **Only two of those are genuinely new causal effects; the other two are automatic consequences of mechanics already fully specified:**

```text
Promotion
   ├──→ Demand modifier          (NEW — fills the slot Document 6 reserved)
   └──→ Order / pre-stocking     (NEW — fills the slot Document 9 reserved)

                                  Sales and Inventory depletion are NOT
                                  separate effects of Promotion — they
                                  follow automatically, via the demand
                                  modifier, through mechanics Documents
                                  6-8 already fully defined.
```

If Sales or Inventory depletion needed their own direct arrow from Promotion, that would mean the existing Demand→Sales→Inventory chain wasn't actually sufficient — which would be a sign something was designed wrong earlier, not a reason to add new arrows now. Keeping this distinction explicit is what keeps Document 10 scoped to filling in two reserved slots rather than re-litigating the whole chain.

## What is a promotion? Origin determines what NovaFoods knows

This is the direct answer to "what does NovaFoods actually observe about it," and it's worth splitting into two categories because they have genuinely different observability, not just different funding:

- **NovaFoods-negotiated promotions** — jointly planned as part of the trade relationship (comparable to Orders: NovaFoods is a direct party to the agreement). The *planned terms* — dates, scope, discount depth — are a Phase 1 fact NovaFoods knows with certainty, because NovaFoods helped set them.
- **Retailer-unilateral promotions** — the retailer runs its own promotion, funded and decided independently. NovaFoods has no advance knowledge of the *planned* terms at all; whatever it learns, it learns the same way it learns anything else about the retailer's business — through Phase 2, later, not designed here.

Both are genuine Phase 1 business events either way — this distinction is about what NovaFoods *knows in advance*, not about which promotions are "more real." It's included because it's a labeling distinction on already-established entities (comparable to how `shares_inventory_visibility` labels a retailer relationship), not a new causal mechanism — it doesn't add the kind of complexity Document 8/9 deferred elsewhere.

**Confirmed: retailer-unilateral promotions are included in Phase 1**, precisely because they create a valuable asymmetry in what NovaFoods knows — a NovaFoods-negotiated promotion can inform expected demand and replenishment ahead of time; a retailer-unilateral one is an actual event NovaFoods may only learn about through imperfect observation, later, if at all.

**Explicit invariant, stated because it's easy to blur:** *NovaFoods not knowing about a promotion in advance is not the same thing as the promotion not existing in Ground Truth.* Phase 1 always knows a retailer-unilateral promotion happened — it's real business reality, generated the same way any other promotion is. What varies is only what Phase 2 later determines NovaFoods actually receives about it. This is the same Latent/Observable architecture the whole project has been built around, applied here rather than reargued.

**A closely related invariant, worth keeping visibly separate from the one above:** *what controls the consumer-demand effect is execution, never NovaFoods' knowledge of the promotion.* These are two different axes entirely —

```text
Did the promotion exist, and was it executed?  → controls consumer demand
Did NovaFoods know about it in advance?        → controls what's knowable to the Decision Platform
```

A retailer-unilateral promotion that's genuinely executed produces a genuine consumer demand increase regardless of whether NovaFoods knew anything about it beforehand — origin governs advance knowledge (this section), `execution_state` governs the demand effect ([next section](#planned-terms-vs-actual-execution--a-second-latent-gap)). The two must never be conflated, or a retailer-unilateral promotion would end up silently unable to affect demand just because NovaFoods wasn't a party to it — which would be wrong; NovaFoods' ignorance has no bearing on what actually happens in the store.

## Planned terms vs. actual execution — a second latent gap

For NovaFoods-negotiated promotions specifically, knowing the planned terms doesn't mean the retailer executes them faithfully — the same shape of problem Document 5 found for assortment (head-office records vs. shelf reality):

- **Planned promotion terms** (Phase 1, exogenous, NovaFoods-known when negotiated) — the agreed dates, scope, discount depth.
- **Actual execution** (Phase 1, **latent**) — whether the store genuinely ran the promotion as agreed: right dates, right display, right price. Causally derived from the planned terms with real variation, not assumed to match perfectly.
- **Retailer-reported execution** (Phase 2, Observable, not designed here) — whatever the retailer's systems say happened.
- **Inference** (not designed here) — the Decision Platform's eventual estimate of whether a promotion actually ran as intended. Analytical Engine milestone's job.

**Confirmed: keep execution simple.** `execution_state` takes one of exactly three values — `executed`, `partially_executed`, `not_executed` — rather than modeling every possible compliance-failure mode (wrong display, wrong price, wrong duration, each independently). Where `partially_executed`, an `actual_start`/`actual_end` sub-range (defaulting to the planned range when fully executed) captures which portion actually ran — enough to drive the demand-modifier window below without turning this into a full trade-promotion-management system.

**This split produces a realistic scenario for free, without designing it directly:** a store pre-stocks *for the planned promotion* (see below — pre-stocking responds to the plan, not to execution), but if execution falls through — the display never goes up, the price never changes at the shelf — demand never gets the lift, and the store is left holding excess inventory it wouldn't otherwise have. That's a genuine, realistic "over-stocked because a promotion was planned but under-executed" situation, and it falls out of keeping the two causal pathways (pre-stocking vs. demand lift) properly separated, the same way phantom inventory fell out of keeping `physical_inventory` and `reported_inventory` separate in Document 8. **Nobody has to tell the eventual recommendation engine "this promotion created excess inventory"** — it has to discover the consequence from the observations, the same way it has to discover everything else this project's Ground Truth deliberately doesn't hand over for free.

## Structure and scope of a Promotion

**Confirmed core attributes** — enough to capture business consequences, deliberately not a full trade-promotion-management system:

```text
Promotion
├── scope              (store-SKU pairs covered — e.g. all stores of a
│                        retailer, or a specific region within it)
├── planned_start, planned_end     (the agreed dates — renamed from an
│                                    earlier effective_from/effective_to
│                                    draft, to keep "planned" distinct
│                                    from "actual" throughout)
├── planned_terms       (type, discount_depth where applicable)
├── origin              (NovaFoods-negotiated | retailer-unilateral)
└── execution_state     (executed | partially_executed | not_executed,
                          with actual_start/actual_end when partial)
```

**Structural rule, mirroring Document 5:** a promotion on a store-SKU pair implies that pair is (or is expected to be) sell-eligible — promoting something a store doesn't carry isn't meaningful.

**`type` simplified to a two-way split, per review** — `PRICE_PROMOTION` or `NON_PRICE_EVENT` — rather than a longer enumerated list. Bundle/multi-buy mechanics, if ever needed, are a variant of `PRICE_PROMOTION`, not a separate top-level type. Still an initial taxonomy, same treatment as every other classification list in this series (Retailer Type, Store Format) — a working starting set, not fixed.

## Effect 1: demand modifier (fills Document 6's slot)

**Proposed:** the promotional modifier in Document 6's multiplicative demand structure is populated here — but **only when a promotion is actually executed, not merely planned.** A planned-but-unexecuted promotion contributes nothing to demand.

**Confirmed: `discount_depth` feeds this promotional demand modifier only — it does not feed Document 6's baseline price-elasticity term.** The promotion is modeled as an independent demand effect (attention, display, purchase timing, and similar), not as a temporary change to the price Document 6's elasticity relationship responds to. Wiring `discount_depth` into both mechanisms would double-count the same promotional effect; keeping them separate also means `discount_depth` never has to reconstruct an actual charged consumer price, consistent with retail shelf pricing remaining out of scope (see [below](#retail-shelf-pricing--still-out-of-scope-not-merely-deferred)).

**Confirmed: a three-phase curve, not a flat step function.**

```text
        promotion window
           │
Demand     │      ┌────────┐
           │     /          \
     ──────┤────/            \──────────
           │  pre    lift      post
           └──────────────────────────→ time

Normal demand = 100/day
  Pre:       90    (anticipation — some pre-buying softens normal demand)
  Promo:    160    (the lift itself)
  Post:      80    (trough — demand pulled forward, not lost)
  Recovery: 100    (back to normal)
```

Three phases, not two, because promotions plausibly do all three: anticipatory pre-buying, an elevated purchase rate during the window, and a post-promotion trough as some of that lift was demand *timing*, not new demand — consumers who stocked up buy less immediately afterward, which is a different phenomenon from consumers liking the product less. **Magnitudes are configurable and stochastic, not a universal hardcoded curve** — different categories and products should be expected to respond differently, consistent with every other generative-formula decision in this series staying qualitative-shape-only, exact parameters left to implementation.

## Effect 2: order / pre-stocking response (fills Document 9's slot)

**Proposed:** pre-stocking responds to the **planned** promotion — a store orders ahead of a known, scheduled promotion, exactly as Document 9's no-lookahead CAN-list already anticipated ("known promotion schedule, if already determined"). This is what makes the planned-vs-executed split above generate its realistic over-stock scenario: the order response doesn't wait to see whether execution actually happens, because in reality a store commits shelf space and places replenishment orders based on the plan, before the promotion window even starts.

## Deliberately not modeled: the state space stops here

Explicit, so the boundary doesn't erode one document at a time: `planned_terms` + `execution_state` is a deliberate first-order approximation, not an incomplete sketch waiting to be filled in. **Not introduced as separate latent variables**, even though each is a real phenomenon in actual retail: consumer awareness, promotional visibility, display compliance, the actual promotional price charged at the register, the actual discount depth realized, advertising exposure. Modeling any of these would explode the state space before the basic planned-vs-executed model has even been validated. If one of them ever proves necessary, it should be added against a demonstrated need — the same discipline this document already applied to the Event entity and Documents 8/9 applied to shrinkage and the distribution-center layer.

## Retail shelf pricing — still out of scope, not merely deferred

Worth being explicit, since this document is the natural place price questions resurface: Document 2's price record is the **wholesale** price NovaFoods charges the retailer — a different thing entirely from the **retail shelf price** a consumer sees. Continuous, non-promotional retail shelf pricing is not modeled anywhere in this project's current scope — not deferred to a future document, genuinely out of scope. This document only introduces a promotional-period `discount_depth` for the promotion's own window, which is enough to drive the demand and ordering effects above without requiring a full always-on retail pricing model underneath it. **`discount_depth` is not intended to reconstruct a fully modeled retail shelf price** — it is an input to the promotional demand modifier only (see [Effect 1](#effect-1-demand-modifier-fills-document-6s-slot) above), which is what keeps this document from quietly pulling a retail-pricing system back into Ground Truth through the back door.

## Events — folded into Promotion, not a separate entity

**Confirmed: unified, no separate Event entity — deliberately deferred, not ruled out.** "Events" (this document's other namesake) are modeled as `NON_PRICE_EVENT`, a Promotion `type`, rather than their own entity. A themed in-store event and a price promotion are structurally the same thing — a scoped, dated, causally-effective business occurrence — differing only in mechanism, which `type` already captures. The governing principle: **don't build an abstract event framework just because we can.** If genuine events surface later that don't actually fit the Promotion shape — a holiday, a new-store opening, a local disruption, a major sporting event — a proper `Event` entity can be introduced then, against real requirements, rather than speculatively now.

**Not this document's job:** general calendar/holiday seasonality (Thanksgiving broadly lifting grocery demand) — that's already Document 6's territory, confirmed there. This document only covers discrete, plannable, scoped occurrences that behave like promotions.

## The acyclicity / no-lookahead rule, reaffirmed

Promotion terms belong to the exogenous "World / Parameters" layer in Document 6 and 9's causal ordering diagrams — decided as part of building the world, before the days they affect, never generated reactively in response to a day's demand or sales. Execution, demand effects, and order effects all derive causally *from* the planned terms; nothing about a promotion is ever inferred backwards from an observed outcome.

## Illustrative example (not a real mechanism)

Purely to make the structure concrete — none of this is a real decision:

```text
BayMart – US, Store #118, RidgeCrest Kettle-Style Sea Salt Chips, 8 oz

Promotion: origin=NovaFoods-negotiated, type=PRICE_PROMOTION, 20% off
  planned_start: 2026-06-01, planned_end: 2026-06-14

Pre-stocking (Document 9): store orders extra ~10 days ahead,
  responding to the planned terms

execution_state: partially_executed
  actual_start: 2026-06-03, actual_end: 2026-06-14
  (2 days late — a real, imperfect execution, not the plan exactly)

Demand modifier (three-phase, applied only to the actual window):
  pre-phase before 06-03, lift 06-03→06-14, trough after
  — no lift at all for 06-01/02, despite the plan, because execution
  didn't actually start until the 3rd

Result: the store received pre-stock sized for a 14-day promotion but
  only got a 12-day demand lift — a small, realistic, unplanned
  inventory surplus, produced without designing "surplus" directly.
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Causal effects from Promotion | Exactly two (demand modifier, order/pre-stocking); Sales and Inventory depletion remain automatic consequences |
| Demand response shape | Three-phase curve (pre-promotion softening, lift, post-promotion trough), configurable/stochastic per category — not a universal hardcoded curve, not a flat step function |
| Post-promotion trough | Represents demand *timing* (pulled forward), not reduced product preference |
| Planned vs. actual execution | Confirmed — kept simple: `executed` / `partially_executed` / `not_executed`, not a full compliance-failure taxonomy |
| Demand lift vs. pre-stocking asymmetry | Confirmed — lift applies only on actual execution; pre-stocking responds to the plan |
| Retailer-unilateral promotions | Included — the asymmetry in what NovaFoods knows in advance is itself valuable |
| Unknown ≠ nonexistent | Explicit invariant — Phase 1 always generates the event; Phase 2 determines what NovaFoods receives about it |
| Separate Event entity | No — deferred, not ruled out; introduce one later only against a real requirement that doesn't fit Promotion |
| Retail shelf pricing | Remains genuinely out of scope |
| Promotion entity scope | Core fields only (scope, planned dates, planned terms, origin, execution state) — not a full trade-promotion-management system |
| `discount_depth` vs. price elasticity | `discount_depth` feeds only the promotional demand modifier (Effect 1) — never Document 6's baseline price-elasticity term. Keeps the two mechanisms independent (avoids double-counting) and keeps retail shelf pricing out of Ground Truth |

## Explicitly out of scope for this document

**M2B / Phase 2:** retailer-reported promotion execution as an actual feed.

**Analytical Engine milestone:** inferring whether a promotion happened from observable signals.

**Implementation:** exact demand-lift magnitudes by type, pre-stocking sizing formulas, and execution-compliance probabilities.

**Out of scope entirely, not deferred:** continuous non-promotional retail shelf pricing.
