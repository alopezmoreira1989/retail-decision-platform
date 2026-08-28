# Document 5 — Assortment

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 6 (Demand) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: four distinct concepts and the (non-deterministic) chain between them — distribution eligibility (retailer level), physical assortment (store level, latent), sell-eligibility (derived, not stored), and availability (whether a SKU can actually be purchased right now) — plus the temporal, business-event nature of assortment change, and the fundamental invariant that assortment and availability are never the same thing.

Does **not** define: demand mechanics (Document 6), sales/POS mechanics (Document 7), inventory/stockout mechanics (Document 8), the generative formulas that turn `store_scale_class` into actual SKU counts (an implementation detail, not a planning-document decision), retailer-reported assortment as a Phase 2 feed (M2B), or the availability-inference algorithm the Decision Platform will eventually run (Analytical Engine milestone).

## The central risk: assortment must never be conflated with observed sales

Stated up front because it's the thing most likely to get quietly gotten wrong: **"this SKU didn't appear in a store's POS data" does not mean "this SKU isn't in that store's assortment."** A zero in POS can mean any of several genuinely different things:

- no consumer demand that day (ordinary zero demand, product is assorted and in stock)
- a stockout (assorted, but truly out of stock right now)
- temporary store closure (Document 4)
- the product simply isn't part of that store's assortment at all
- a retailer reporting problem or feed failure (Phase 2, doesn't reflect reality at all)

If assortment were ever defined as "whatever shows up in POS," several of these cases would become indistinguishable, and the entire "possible availability issues" recommendation type from the project's recommendation philosophy would collapse into a tautology — there'd be nothing left to infer. Assortment has to be its own independent Phase 1 fact, generated on its own terms, precisely so that later documents can meaningfully ask "does observed behavior look consistent with what we'd expect given the true assortment" rather than defining the answer into existence. See [Fundamental invariant: assortment ≠ availability](#fundamental-invariant-assortment--availability) below — this is the same point, stated as a hard rule once the full concept set is on the table.

## The chain, mapped to Phase 1 / Phase 2 / Inference

```text
NovaFoods product universe (Document 2)
        ↓
Distribution eligibility            — Phase 1, retailer-level, NovaFoods' own commercial decision
        ↓  (not deterministic — see below)
Physical assortment                 — Phase 1, store-level, LATENT
        ↓  (retailer may separately report an assortment/planogram signal — Phase 2, OBSERVABLE, not designed here)
        ↓  (Decision Platform infers likely availability — INFERENCE, not designed here)
        ↓  (not deterministic — see below)
Sell-eligibility                    — derived, not stored (assortment AND product lifecycle AND store lifecycle)
        ↓  (not deterministic — see below)
Availability                        — can it actually be purchased right now; depends on true stock (Document 8, not designed here)
        ↓
Observed POS                        — Document 7, downstream of demand, availability, and Phase 2 reporting
```

Each arrow is a distinct causal step, not a formality — see [The four concepts, side by side](#the-four-concepts-side-by-side) for why none of them are deterministic. The layers that most need care — because they're where the "don't conflate with sales" risk actually lives — are physical assortment, sell-eligibility, and availability.

## Layer 1: NovaFoods product universe

Already fully defined — Document 2's SKU catalogue. Nothing added here.

## Layer 2: Distribution eligibility (retailer level)

**Confirmed:** a Phase 1 fact — which SKUs NovaFoods has decided to make available for a given retailer to order at all. This is NovaFoods' own trade/distribution decision (e.g., a club-pack SKU might only be offered to Wholesale-format retail relationships; a limited-distribution product might be offered to a subset of retailers), not something requiring observation of an external party — NovaFoods knows its own distribution decisions with certainty by construction, so this needs no Latent/Observable split, unlike the next layer.

**Confirmed to live at the retailer level for now**, not per-store or per-banner/region, consistent with the established pattern of not introducing granularity without a demonstrated need (Document 3/4's precedent). The data model should stay extensible enough to support a future `Retailer → Banner → Region → SKU` hierarchy without redesign, but that hierarchy is **not designed now** — flagged as a plausible future refinement only.

**Distribution eligibility and physical assortment are two different decisions, made by two different parties, and they can diverge:**

```text
NovaFoods decides:  "SKU X is distributed to Retailer A"      → distribution eligibility
Retailer/store reality:  "Store 104 actually carries SKU X"   → physical assortment
```

Distribution eligibility = YES and physical assortment = NO is a normal, expected combination — it just means a particular store chose not to carry something it was allowed to. A structural rule still holds in the other direction: `physical_assortment(store, sku)` implies `distribution_eligibility(store.retailer, sku)` — a store can't carry a SKU its retailer was never offered. Country compatibility is already handled structurally (Document 2's SKUs and Document 3's retailers are both country-scoped) and doesn't need to be separately re-decided here.

## Layer 3: Physical assortment (store level) — extending Latent → Observable → Inference again

This is where the real design decision is. The first instinct might be to treat "which SKUs a store carries" as simple, reliably-known master data — but that would repeat the exact mistake Document 4 caught and corrected for store classification. The same reasoning applies here, maybe even more directly: a retailer's head-office systems can say a store is authorized to carry a SKU while the store's actual shelf reality diverges (a well-known real phenomenon — planogram compliance gaps), and even where systems agree, NovaFoods only ever receives what the retailer's systems report.

**Confirmed — same three-way split as Document 4's `store_scale_class`:**

- **`physical_assortment`** (Phase 1, **Latent**) — the ground truth of which SKUs are genuinely, physically carried by a specific store, at a specific time. Named to parallel Document 1's `physical inventory` deliberately — same shape, same tier. Generated by Phase 1's own mechanics (informed by `store_scale_class` and `format` — see below), and never handed to the Decision Platform directly.
- **Retailer-reported assortment** (Phase 2, **Observable** — flagged here, not designed here) — whatever a retailer's systems tell NovaFoods a store carries (a planogram or store/product master feed). Correlates with physical assortment but isn't guaranteed to match it, the same way reported inventory correlates with but isn't physical inventory.
- **Availability inference** (**Inference**, not Phase 1 at all) — the Decision Platform's estimate of whether a SKU is likely actually available at a store, drawing on reported assortment plus other observable signals (POS patterns, orders). This is precisely the project's existing "possible availability issues" recommendation type — not a new concept, just its ground-truth counterpart made explicit. Belongs to the Analytical Engine milestone, not this document.

**Qualitative link to Document 4 (no formula decided here):** `store_scale_class` and `format` plausibly influence assortment breadth and category mix — a higher-scale store plausibly carries more SKUs, a Convenience-format store plausibly carries a narrower, different category mix than a Hypermarket-format store. The document only states this as a qualitative causal principle Phase 1's generative mechanics should respect; the actual generative formula (how many SKUs, which ones) is an implementation decision, not something to pin down in a planning document.

## Temporal structure: assortment changes are genuine business events

Per the project's existing business-reality/data-error distinction, "a store starts or stops carrying a product" is Phase 1 reality, not a Phase 2 phenomenon:

| Phase 1 (changes physical assortment) | Phase 2 (never changes physical assortment) |
|---|---|
| A store adds a new product to its shelf | A retailer's assortment feed fails to mention a SKU this week |
| A store discontinues carrying a product locally | A retailer's planogram file is stale or late |
| A store's planogram reset changes its category mix | A retailer misreports what a store carries due to a system error |

**The acyclicity rule applies here too — added retroactively, since this document predates Document 6's generalization of it.** A store adding or discontinuing a SKU must be generated from exogenous or already-generated-upstream causes (store attributes, retailer decisions, a planogram reset schedule) — never from that store-SKU pair's own downstream Sales or Demand history. It would be tempting to implement "drop this SKU once its sales have been low for a while" as a trigger, but that's precisely the violation Document 6 later named: generating an earlier-in-the-chain quantity (assortment, which itself gates whether Sales can happen at all) from a later one (Sales) that depends on it. The same canonical ordering applies here as everywhere downstream of it:

```text
World / Parameters → Physical assortment → Sell-eligibility → ... → Sales
```

**Confirmed: no third assortment state — effective dating instead.** A store-SKU pair carries `effective_from` and `effective_to` (nullable):

```text
Store 104, SKU 873
  effective_from: 2026-01-01
  effective_to:   2026-06-30

Store 104, SKU 873   (same store, same SKU, later)
  effective_from: 2026-09-01
  effective_to:   NULL
```

The gap between the two rows — July and August, in this example — *is* the period the SKU wasn't part of the store's physical assortment. Nothing needs to represent that gap explicitly; the absence of a covering row already means it.

**Why this differs from Document 2's Product lifecycle, stated explicitly:** Product lifecycle (`ACTIVE` / `TEMPORARILY_UNAVAILABLE` / `DISCONTINUED`) is a **state of the product itself** — one thing, changing over time. Assortment is not a state of anything; it's a **time-varying relationship between Store and SKU**. A relationship doesn't need a "temporarily off" state the way a single entity's lifecycle might — it just has periods where the relationship holds and periods where it doesn't, expressed as rows with date ranges. A SKU leaving and later returning to a store's assortment is not a special case requiring its own state; it's just a second row. This is also why it doesn't need Document 4's `TEMPORARILY_CLOSED`-style justification — that question (is there a real, common enough middle-state phenomenon?) only applies to entity lifecycles, and assortment isn't one.

**Confirmed: no identity implications.** Re-adding a previously-dropped SKU to a store's assortment is unremarkable and creates no new identity — unlike Product or Store, a store-SKU assortment pairing isn't an "identity" with continuity concerns; it's just a relationship fact that can be re-asserted.

## Layer 4: Sell-eligibility — derived, never stored

**Confirmed:** not a new attribute anywhere. A store-SKU pair is sell-eligible on a given day if and only if:

```text
physical_assortment(store, sku, date) is true   (a covering effective_from/effective_to row exists)
  AND product lifecycle state is ACTIVE (Document 2)
  AND store lifecycle state is OPEN (Document 4)
```

Deliberately computed, not stored — storing it as its own field would create a second source of truth that could silently drift out of sync with the three things it depends on. This answers "could this genuinely be sold today" — a legal/business-eligibility question, still one step short of "can it actually be purchased right now" (Layer 5, Availability).

## Layer 5: Availability — named here, not designed here

**Confirmed as an explicit fourth concept**, not folded into sell-eligibility. A SKU is available if it's sell-eligible *and* there is actual physical stock right now:

```text
Available = sell-eligible AND physical_inventory(store, sku, date) > 0
```

`physical_inventory` is Document 8's job entirely — nothing about inventory mechanics is designed here. This document only insists that **Availability is named as its own concept**, distinct from sell-eligibility, because collapsing them would silently reintroduce the exact conflation this document exists to prevent: a sell-eligible SKU with zero stock is *not* available, and that's a completely different situation from a SKU that was never sell-eligible in the first place. See [Fundamental invariant](#fundamental-invariant-assortment--availability) below.

## The four concepts, side by side

| Concept | Meaning |
|---|---|
| Distribution eligibility | NovaFoods allows/offers the SKU to the retailer |
| Physical assortment | The store actually carries the SKU |
| Sell-eligibility | The SKU is legally/business-wise eligible to be sold at that store, at that time |
| Availability | The SKU can actually be purchased right now |

The chain runs in that order, but **none of the arrows are deterministic** — each concept can be YES while the next is NO:

```text
Distribution = YES, Assortment = YES, Sell-eligible = YES, Availability = NO
  → the product is out of stock (a genuine stockout, Document 8)

Distribution = YES, Assortment = NO, Sell-eligible = NO, Availability = NO
  → the store simply doesn't carry the product — a completely different situation
    that happens to end in the same "not available" outcome
```

Both examples end at "not available," but for entirely different reasons — which is exactly why all four concepts have to be kept separate rather than collapsed into one "is it available" flag.

## Fundamental invariant: assortment ≠ availability

The single rule this document exists to establish, stated as plainly as possible: **a store can genuinely carry a product and still have none of it in stock today.**

```text
Physical assortment = YES
        ↓
Inventory = 0
        ↓
Currently available = NO
```

versus:

```text
Physical assortment = NO
        ↓
(inventory is trivially 0 — nothing to stock)
        ↓
Currently available = NO
```

Both end at "not available" — but the first is a stockout (an assorted product genuinely out of stock, a real recommendation opportunity) and the second is a product that was never part of the store's offering at all (nothing wrong is happening; there's no assortment gap to fix). Confusing the two — most commonly by using POS absence as evidence that a product isn't assorted — is exactly the mistake this document is built to prevent. This distinction becomes load-bearing again in Document 8 (Inventory) and in the recommendation engine's availability-issue logic later.

## Layer 6: Observed POS — not this document's job

Flagged only, to close the chain: observed POS (Document 7) depends on availability *and* true consumer demand *and* Phase 2 reporting fidelity. None of those mechanics are designed here. The point of drawing the full chain in this document is so that when Document 7 is written, "sales" is never accidentally treated as a proxy for "assortment" or "availability" — they sit at opposite ends of a chain with real, distinct, causally meaningful steps in between.

## Illustrative example (not a final mechanism)

Purely to make the chain concrete — none of this is a real decision:

```text
NovaFoods SKU: RidgeCrest Kettle-Style Sea Salt Chips, 8 oz bag, US
        ↓
Distribution eligibility: BayMart (US) — eligible
        ↓
BayMart Store #118 (Round Rock, TX)
  physical_assortment: effective_from 2024-03-01, effective_to: null (still carried)
        ↓
Product lifecycle: ACTIVE · Store lifecycle: OPEN
        ↓
sell-eligible: true
        ↓
physical_inventory (Document 8, not designed here): suppose 0 today
        ↓
available: false — a stockout, not an assortment gap
        ↓
[Document 7's job from here]
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Physical assortment latent/observable/inferred? | Yes — same three-way split as `store_scale_class` |
| Temporary delisting state? | No — use effective dating (`effective_from`/`effective_to`); assortment is a time-varying relationship, not an entity with a lifecycle |
| Distribution eligibility granularity | Retailer-level initially |
| Banner/region hierarchy | Plausible future extension; not designed now |
| Assortment ≠ availability | Fundamental invariant — see dedicated section above |
| Assortment can disappear and return | Yes, via a second `effective_from`/`effective_to` row; no special handling needed |
| Product identity changes when assortment changes? | No — assortment is a Store–SKU relationship fact, not an identity |
| Sell-eligibility | Derived, never stored |
| Availability | Named as an explicit fourth concept, distinct from sell-eligibility; mechanics deferred entirely to Document 8 |
| Generative formula for assortment breadth/mix | Not decided here — only the qualitative link to `store_scale_class`/`format` |

## Explicitly out of scope for this document

**Document 6:** demand mechanics — how sell-eligibility, store/geography characteristics, and availability translate into actual generated demand.

**Document 7:** sales/POS mechanics.

**Document 8:** true stock and stockouts — `physical_inventory`, the mechanic Availability depends on, is entirely Document 8's job, not designed here.

**M2B / Phase 2:** retailer-reported assortment as an actual feed, its cadence, and its fault characteristics.

**Analytical Engine milestone:** the availability-inference algorithm — reconciling retailer-reported assortment (and other observable signals) into an actual estimate of likely availability.

**Implementation, not this document:** the generative formula translating `store_scale_class`/`format` into actual SKU counts and category mix.
