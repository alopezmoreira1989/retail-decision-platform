# Document 6 — Demand

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 7 (Sales / POS Reality) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: the generative mechanics for consumer demand — already established as Latent back in Document 1, but not yet designed. Covers granularity, the two-stage potential-demand/actual-demand structure carried forward from Document 4, store-level and product-level demand drivers, seasonality (distinct from Document 2's product-level `is_seasonal`), regional effects and store-to-store correlation, and where price and promotions plug in.

Does **not** define: sales/POS mechanics — how demand becomes an observed sale (Document 7); true stock and stockouts (Document 8); promotional mechanics (Document 10, though this document leaves room for them); exact numeric formulas, distributions, or parameters (implementation, not a planning-document decision); or product substitution/cannibalization effects (flagged as a real phenomenon, explicitly deferred — see below).

## Recap: demand was already Latent from Document 1 — this document is new mechanics, not a new architectural call

Document 1 named consumer demand as Latent on day one; that's not reopened here. What's new in this document is *how* Phase 1 actually generates it, and the discipline required to do that without repeating Document 4's mistake.

## The non-circularity principle, generalized beyond Document 4

Document 4 established the chain `store_scale_class → potential demand → actual demand → sales` and a hard requirement: no deterministic mapping from the structural driver to the outcome, or the hidden variable becomes trivially rediscoverable from observed sales. That requirement governs this entire document.

**Confirmed, and stated more generally than an earlier draft of this document had it:** a rule scoped to "don't read previous sales" is too narrow — it can be technically satisfied while still being violated in spirit, e.g. by computing a derived feature from historical sales and feeding *that* into demand generation instead of sales directly. The rule has to be stated at the level of causal ordering, not a specific forbidden table:

> **Phase 1 generators must not consume any Phase 1 output that is downstream of the variable currently being generated.**

The causal direction is one-way and unambiguous, and nothing later in the chain may feed back into anything earlier — not directly, and not indirectly through a derived feature:

```text
WORLD / PARAMETERS
        ↓
POTENTIAL DEMAND
        ↓
ACTUAL DEMAND
        ↓
SALES
        ↓
OBSERVED POS
```

Never `SALES → DEMAND`, and never `SALES → (derived feature) → DEMAND` either — the derived-feature version is the same violation wearing a disguise, not a loophole.

## Scope: demand is generated for sell-eligible store-SKU-day triples

**Confirmed:**

> Phase 1 generates demand only for store–SKU pairs that are eligible to sell the SKU. Notional demand for non-assorted pairs is deferred until a future assortment-optimization use case requires it.

Generating demand for a non-assorted store-SKU pair would introduce a latent variable with no necessary operational manifestation, unnecessarily complicating the `assortment → demand → sales` chain. If a future recommendation type (e.g., "should this store carry this SKU") needs an unmet-demand concept, that's an additive capability layered on top later — not something to fold into the base generative model now, which would mean pulling a future application's needs into today's ground truth.

## Granularity

**Proposed:** store × SKU × day, denominated in units — the canonical convention Document 2 already established (consumer sellable eaches at the SKU level). This matches CLAUDE.md's "daily minimum" resolution requirement for Phase 1.

**Deliberately not modeled:** a full shopper-journey decomposition (store traffic × basket composition × conversion). Demand here is a single figure — "how many units of this SKU this store's true consumer demand would want to buy this day, if fully available" — not a multi-stage shopper behavior model. Flagged as a scope simplification, not an oversight; a richer model could be introduced later if it turns out to matter.

## The shape of the demand model — structure, not a formula

**Confirmed as a two-stage, multiplicative structure**, matching Document 4's exact chain language. The split is worth keeping specifically because it separates two conceptually different questions — "what structural demand level does this store-SKU have" vs. "how much demand actually occurred this day" — which is exactly the kind of separation that keeps the ground truth from being trivially recoverable from sales, the same concern that shaped Document 4's `store_scale_class`:

```text
Potential demand   (structural baseline — store × product, relatively stable)
        ↓  × seasonal modifier × regional modifier × (promotional modifier, Document 10) × noise
Actual demand      (day-specific, realized)
        ↓  capped by availability (Document 5/8) — Document 7's job
Sales
```

**Potential demand** is the relatively stable, structural capacity a store-SKU pair has to sell — driven by store and product characteristics (below). **Actual demand** is what a specific day actually produces once seasonal, regional, promotional, and idiosyncratic (noise) factors are applied. Only the *shape* of this decomposition (multiplicative, staged) is proposed here — exact functional forms, coefficients, and distributions are implementation decisions, consistent with how Documents 4 and 5 treated their own generative formulas.

**Note the price-elasticity term is deliberately absent from the potential → actual multiplier list above.** Price is baked into potential demand once, through the product popularity factor ([below](#product-level-demand-potential)), and must not reappear as a second, separate multiplier at the actual-demand stage — only the seasonal/regional/promotional/noise modifiers apply there.

## Store-level demand potential

**Proposed:** `store_scale_class` and `format` (Document 4) are inputs to potential demand, but not the whole story. Operationalizing Document 4's non-determinism requirement concretely: **each store gets its own individual baseline demand level, drawn from a tier-appropriate range or distribution — not a fixed value per tier.** Two stores in the same `store_scale_class` should show real, substantial spread in their actual potential demand. If they didn't, `store_scale_class` would be fully recoverable from observed sales alone, which is exactly what Document 4 ruled out.

## Product-level demand potential

**Proposed:** each SKU carries its own individual popularity factor, not fully determined by category, brand, or price alone — two SKUs in the same subcategory are expected to sell differently in practice, and that variation should exist independent of any single attribute.

**Price** — meaning NovaFoods' modeled wholesale/list price (Document 2), not a retail shelf price, which this project does not model (confirmed in Document 10) — is proposed as a directional input to *potential* demand only: higher price generally associated with lower baseline demand, all else equal. The actual elasticity function (magnitude, curve shape, category-specific sensitivity) is an implementation decision, not designed here.

**Confirmed: this price relationship is structurally independent from Document 10's promotional demand modifier.** `discount_depth` drives the promotional modifier applied to *actual* demand (see [Promotional lift](#promotional-lift--flagged-not-designed) below) — it does not feed back into this baseline price-elasticity term. Wiring `discount_depth` into both would double-count the same promotional effect: once as a lower effective price, once as a promotional lift.

## Seasonality — distinct from Document 2's `is_seasonal`

Worth being explicit about the difference, since the two concepts sound similar but aren't: Document 2's `is_seasonal` flag governs whether a *product exists* on shelf during a given window (an availability/lifecycle-adjacent concept — a pumpkin-spice flavor that simply isn't sellable outside its window). **This document's seasonality is about demand *intensity* fluctuating over time for every product, seasonal or not** — ordinary year-round chips still sell more some weeks than others.

Proposed: weekly (day-of-week) and annual cyclicality as modifiers on potential demand, country-specific per Document 1's confirmed country-specific calendars (US and Canada holidays differ). Holiday effects (spikes and dips around specific dates) are included as part of this, not a separate mechanism.

## Regional effects and store-to-store correlation

**Confirmed, at the level of a statistical property rather than a concrete definition:**

> Stores sharing the same region must receive correlated demand shocks, while stores in different regions should have lower correlation.

That's the whole requirement this document settles. It deliberately does **not** decide what `region` concretely means — climate zone, sales territory, a simple North/South split, or something else — since that's a Store Universe (Document 4) or implementation concern, not a Demand concern. This isn't a new idea; it's already promised in `docs/SIMULATION.md`'s original description of the hidden state ("store-to-store correlation... rather than independent random draws per row"), and this document is where that promise gets turned into an actual, checkable requirement rather than staying aspirational language.

## Promotional lift — flagged, not designed

**Proposed:** the demand model's multiplicative structure leaves an explicit slot for a promotional modifier, but its mechanics (lift magnitude, duration, decay) are entirely Document 10's job. Mentioned here only so Document 10 has a defined place to plug into, not to pre-design it. **This slot is independent of the price input above** — it represents promotion-specific effects (attention, display, purchase timing) rather than a price change, and must not be merged with the price-elasticity term.

## Explicitly deferred: product substitution and cannibalization

**Confirmed deferred.** A real phenomenon — if a SKU is unavailable, some of its demand plausibly shifts to a substitute rather than simply vanishing — but modeling it properly means defining which products substitute for which, substitution intensity and direction, and possibly cross-elasticities: a materially more complex generative model (price A, promotion A, and demand A would all start interacting with demand B) for little return at this stage.

> Substitution and cannibalization are intentionally excluded from Phase 1. Their omission is a known limitation rather than an assumption that they do not exist.

Recorded explicitly so that a future document doesn't rediscover this as an oversight — it was considered and deliberately deferred, not missed.

## Relationship to Sales — not this document's job

To close the loop cleanly: this document produces **actual demand**. Turning that into **sales** requires capping it by availability (Document 5's derived concept, ultimately gated by Document 8's true stock) — that capping mechanism, and everything about how a sale gets recorded, belongs to Document 7. Nothing about sales mechanics is decided here.

## The Inference-tier counterpart, named for closure

Document 1's original table already named `Expected demand` as the Inference-tier counterpart to latent consumer demand — not a new concept, just noted here for completeness: the Decision Platform's own estimate of demand (from observable signals: POS, orders, reported assortment) is a separate, later Analytical Engine concern, not something this document produces or hands over.

## Illustrative example (conceptual, not a real mechanism)

Purely to make the structure concrete — none of this is a real decision:

```text
BayMart Store #118 (store_scale_class: 4, Hypermarket format)
  × RidgeCrest Kettle-Style Sea Salt Chips, 8 oz, US
        ↓
Potential demand: store baseline (drawn from Tier-4 range, this store's own value)
                   × product popularity factor for this SKU
        ↓
Actual demand (a Tuesday in March, no promotion active):
  potential demand × weekly modifier (Tuesday) × regional modifier (this store's region)
  × substantial random variation
        ↓
[Document 7's job from here: cap by availability → sales]
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Demand for non-assorted SKUs? | No — scoped to sell-eligible triples only; unmet-demand-for-assortment-optimization deferred to a future use case, not folded into the base model now |
| Potential → actual split? | Yes, kept — separates "structural capacity" from "what happened this day," which is exactly what keeps the ground truth from being trivially recoverable from sales |
| No shopper-journey decomposition | Confirmed — a single demand figure per store-SKU-day |
| Store/product-level individual variation | Confirmed required, not just tier/category averages |
| Price | Directional input to potential demand only (modeled wholesale/list price, not retail shelf price); elasticity mechanics are implementation |
| Seasonality vs. `is_seasonal` | Confirmed distinct — intensity variation vs. existence window |
| Regional correlation | Confirmed as a **statistical property** ("same-region stores correlated, cross-region less so"), with the concrete definition of `region` deliberately left to Document 4/implementation |
| Promotional lift | Structurally accommodated, not designed — Document 10's job; structurally independent from the price-elasticity term, so `discount_depth` is never also wired into price (avoids double-counting) |
| Substitution/cannibalization? | Deferred explicitly — a known limitation, not an assumption that it doesn't exist |
| Causal acyclicity rule | **Generalized**: Phase 1 generators must not consume any Phase 1 output downstream of the variable being generated — not just "don't read sales," which could be technically satisfied while violated via a derived feature |

## Explicitly out of scope for this document

**Document 7:** sales/POS mechanics — how actual demand, capped by availability, becomes a recorded sale.

**Document 8:** true stock and stockouts — the mechanism that caps demand into sales.

**Document 10:** promotional lift mechanics — magnitude, duration, decay.

**Implementation, not this document:** exact functional forms, coefficients, distributions, and the regional-correlation mechanism.

**Deferred, not scoped:** product substitution and cannibalization effects.
