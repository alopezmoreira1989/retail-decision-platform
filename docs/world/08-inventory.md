# Document 8 — Inventory

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 9 (Orders / Replenishment) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: `physical_inventory` as the formalized Phase 1 latent ground truth (the `true_stock` placeholder informally used in Documents 5 and 7 has been fully replaced by this name — see [Terminology cleanup](#terminology-cleanup)), its state-transition mechanics across days, why it needs the full three-way Latent/Observable/Inference split that Sales explicitly did *not* need, unmet demand and true stockout events as Ground Truth facts, and the boundary with retailer-reported inventory (Phase 2).

Does **not** define: replenishment order logic — when and how much a store orders (Document 9, and this document has an acknowledged forward dependency on it for the "delivery" input); retailer-reported inventory as an actual Phase 2 feed, its cadence, or staleness characteristics (M2B); the availability-inference algorithm that estimates likely inventory state from observable signals (Analytical Engine milestone).

## The central risk, stated first: physical inventory must never become something the Decision Platform reads directly

This is the concern this document exists to resolve, stated as plainly as the concern that opened Documents 5 and 7: **it would be very easy — even "just for now, as a simplification" — to let a planning or implementation shortcut quietly expose true inventory to the production-like pipeline.** That must never happen, not even temporarily, not even for a vertical-slice shortcut. Physical inventory joins consumer demand as one of the two things Document 1 named Latent from the very beginning of this project, and everything below exists to make that boundary concrete enough that it can't be casually crossed later.

## Why Inventory needs the three-way split that Sales explicitly didn't

Document 7 concluded Sales doesn't need a Latent/Observable/Inference split, because there's no structural reason truth and observation diverge beyond ordinary Phase 2 degradation — a hypothetically perfect feed would just report the truth. **Inventory is the opposite case, and it's worth stating exactly why, given the two conclusions sit right next to each other:** even a retailer reporting its own inventory in complete good faith, with a technically perfect Phase 2 feed, is only reporting what *their own systems* believe the stock to be — and that belief can diverge from physical reality for reasons that have nothing to do with data transmission: stock sitting in the backroom that hasn't been counted onto the shelf, cycle-count lag, timing mismatches between a sale and a system update, shrinkage. This is the same shape of problem `store_scale_class` and `physical_assortment` had — a structural gap between truth and its best-faith representation — not the shape Sales had.

**Confirmed: the three-way split already established in Document 1 stands, now formalized:**

- **`physical_inventory`** (Phase 1, **Latent**) — the true, physical stock at a store for a SKU on a given day. Never exposed to the Decision Platform.
- **Retailer-reported inventory** (Phase 2, **Observable**, flagged here, not designed here) — gated by Document 3's `shares_inventory_visibility`: a retailer with `false` sends nothing at all; a retailer with `true` sends a proxy, never the truth with certainty.
- **Likely inventory state** (**Inference**, not Phase 1, not designed here) — the Decision Platform's eventual estimate, drawing on reported inventory (if any), sell-out patterns, order history/cadence, and commercial-visit feedback — the exact combination Document 1 originally sketched. Analytical Engine milestone's job.

## Two fundamentally different kinds of uncertainty

Worth naming explicitly, because it's the precise reason Documents 7 and 8 reached opposite conclusions sitting right next to each other. POS and Inventory don't just happen to have different fault rates — they have **different kinds of gap** between truth and what NovaFoods could ever receive:

```text
POS — observation uncertainty only

Actual Sale
    ↓
Retailer records the sale
    ↓
Perfect feed
    ↓
NovaFoods sees the actual sale
```

```text
Inventory — state-representation uncertainty, before observation even enters the picture

Physical inventory
    ↓
Retailer's own operational system's belief about it   ← the gap is already here
    ↓
"Reported inventory"
    ↓
Perfect feed
    ↓
NovaFoods
    ↓
Reported inventory ≠ necessarily physical inventory
```

**Observation uncertainty** is what a bad or missing feed does to an otherwise-accurate underlying record — Sales' only failure mode. **State-representation uncertainty** is different in kind: the retailer's *own system* may not accurately represent physical reality even before anything gets transmitted, because inventory is something a system has to be *told about* (via counts, scans, adjustments) rather than something that's definitionally true the moment it happens, the way a completed sale is. A perfect feed fixes the first kind of uncertainty entirely. It does nothing at all for the second. This distinction is what the eventual Decision Platform will need to reason about differently for POS-shaped problems versus inventory-shaped problems.

## Formalizing `physical_inventory`

**Proposed:** `physical_inventory(store, sku, day)`, denominated in the same canonical units as everything else (Document 2's consumer sellable eaches) — already anticipated in Document 1 ("proposed to be internally denominated in the same 'units' convention as sales, for consistency"), now confirmed rather than merely proposed. Daily granularity, snapshot-based — consistent with the state-transition model Document 7 already committed to (Demand[t] and Inventory[t] as independent inputs converging at Sales[t]; Sales[t] plus Deliveries[t] producing Inventory[t+1]).

**Convention: represents sellable stock, not a store's total physical holdings.** This lines up with CLAUDE.md's own canonical-unit example ("store-front-only stock") and matters directly for Phase 2 realism later: a retailer that reports combined store+backroom figures isn't lying, it's using a different — and, per Document 1's canonical-semantics principle, reversible — convention. That distortion is flagged for M2B, not designed here; Phase 1 only needs to commit to one fixed meaning, which this section does.

## The state-transition mechanics

**Proposed**, matching Document 7's confirmed shape exactly:

```text
physical_inventory[t+1] = physical_inventory[t] − Actual Sales[t] + Deliveries[t]
```

**`Deliveries[t]` is an external input from Document 9, not designed in this document** — the same forward-dependency pattern already used twice (Document 5 → Document 8 for `physical_inventory` itself; Document 7 → Document 8 for "stock available at start of day"). Document 8 only defines how inventory *responds* to a delivery arriving, not when a store decides to order or how much — that's Document 9's job entirely, including what "initial stocking" means when a SKU first enters a store's assortment (effectively just the first delivery, not a separate mechanism).

**Inventory can never go negative, and this isn't a new rule — it falls out of Document 7's own definition.** Because `Actual Sales[t] = min(Actual Demand[t], physical_inventory[t])`, the subtraction `physical_inventory[t] − Actual Sales[t]` is always ≥ 0 by construction. Worth stating explicitly so nobody adds a defensive floor/clamp later that isn't actually needed.

## Unmet demand and true stockout events — generated here, consumed by evaluation later

**Confirmed:** whenever `Actual Demand[t] > Actual Sales[t]`, the difference is unmet demand for that store-SKU-day, and a day where `physical_inventory[t] = 0` with positive unmet demand is a **true stockout event**. This directly extends what the project's own early planning already committed to (the original "Implement sales generation" work explicitly called for stockout events to be "recorded and queryable by the evaluation harness only") — this document is where that commitment gets formalized against the now-fully-developed Demand/Sales/Inventory chain.

```text
Demand = 100
Physical inventory = 60
        ↓
Sales = 60
        ↓
Unmet demand = 40
        ↓
Stockout event = TRUE
```

**A deliberate separation of responsibilities, stated explicitly so it doesn't get blurred later:** the event *exists* in the Ground Truth because it's a direct, mechanical consequence of the physical inventory state defined in this document — that part belongs here. *How* the evaluation framework later consumes that event (what "correctly identified" means, what counts as a scoring match, precision/recall definitions) is a separate concern for whenever evaluation architecture is designed, and is explicitly not decided in this document. Generating the event and deciding how it's scored are two different jobs; this document only does the first.

**The production platform must never receive `unmet_demand` or the stockout flag.** These exist exclusively for the evaluation harness — the ground truth the eventual "possible availability issues" recommendation type gets scored against — per the hard Hidden Ground Truth boundary already established project-wide.

## Retailer-reported inventory — flagged, not designed

Nothing new architecturally: this is Document 1's `reported_inventory` and Document 3's `shares_inventory_visibility`, now situated against a fully-specified `physical_inventory`. A retailer with `shares_inventory_visibility: false` contributes nothing here at all; where `true`, the reported figure is Phase 2's problem to degrade (cadence, staleness — most naturally *biased stale*, i.e. lagging physical reality in a specific direction, though the exact fault mechanics belong to M2B, not this document).

## Likely inventory state — named for closure

Document 1 already sketched this combination — sell-out trends, standard order-size/cadence assumptions, commercial-agent visit feedback — as how NovaFoods could estimate inventory without a trustworthy direct feed. Nothing about the estimation method is designed here; this section exists only so the Inference tier has a named home, consistent with how Documents 4–7 each closed their own Latent variable's loop.

## Confirmed deferred: shrinkage and shelf-execution gaps

**Confirmed: defer both**, for the initial Ground Truth. Two real phenomena that would make the state-transition equation above incomplete in a fully realistic simulation:

- **Shrinkage** — theft, damage, spoilage, counting/cycle-count error. A genuine Phase 1 business phenomenon (things that actually happen to physical stock), not a data-system error, if modeled at all.
- **Shelf-execution gaps** — stock physically present in a backroom but not yet moved to the sellable shelf, which is exactly the split this document chose not to make when it defined `physical_inventory` as a single combined "sellable stock" quantity rather than separate store-front/backroom figures.

Adding either now would introduce another latent state and another causal mechanism before the basic system is validated — and it isn't needed to generate the platform's central scenario. A single combined `physical_inventory`, contrasted with retailer-reported inventory and Observed POS, already produces the interesting case on its own:

```text
Physical inventory = 0
Retailer-reported inventory = 15
Observed POS = 0
```

That's already a genuine phantom-inventory-style problem — no shelf/backroom split required to get there. Both remain a documented **future extension**, not an assumption that real stores don't experience them:

```text
physical_inventory = 20
    backroom = 15
    shelf    = 5
    consumer-accessible = 0
```

If shelf execution is ever modeled, it extends the existing architecture (`physical_inventory` decomposes into `backroom_inventory` → `shelf_inventory` → consumer availability) rather than replacing it.

## Illustrative example (not a real mechanism)

Purely to make the state transition concrete — none of this is a real decision:

```text
BayMart Store #118 × RidgeCrest Kettle-Style Sea Salt Chips, 8 oz, US

Day 1:  physical_inventory[start] = 60
        Actual Demand = 100 → Actual Sales = min(100, 60) = 60
        Deliveries = 0
        physical_inventory[end] = 60 − 60 + 0 = 0
        → unmet demand = 40 → true stockout event recorded (evaluation-only)

Day 2:  physical_inventory[start] = 0
        Actual Demand = 45 → Actual Sales = min(45, 0) = 0
        Deliveries = 80 (Document 9, not designed here)
        physical_inventory[end] = 0 − 0 + 80 = 80
```

## Terminology cleanup

`true_stock`, used informally in Documents 5 and 7 before this document formalized the concept, has been replaced with `physical_inventory` everywhere it appeared. The project now has exactly two names for this side of the model — `physical_inventory` (latent reality) and `reported_inventory` (retailer observation) — not three.

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| `physical_inventory` naming | Approved — and back-propagated into Documents 5 and 7, replacing `true_stock` |
| Latent/Observable/Inference split for Inventory | Confirmed, for structurally different reasons than Sales explicitly didn't need it |
| Store-front-only convention | Approved — keeps Document 7's and this document's equations clean and auditable |
| Combined `physical_inventory` (no store-front/backroom split) | Confirmed — sufficient for Documents 7–9; the objective is "can the consumer buy it," not a full store-operations simulator |
| Shrinkage | Deferred — a documented future extension, not an assumption it doesn't happen |
| Shelf-execution gaps | Deferred — same treatment as shrinkage |
| Stockout / unmet-demand event generation | Confirmed — generated here, in the Ground Truth, as a mechanical consequence of `physical_inventory` |
| How evaluation consumes those events | Explicitly *not* decided here — a separate concern for whenever evaluation architecture is designed; no dedicated document needed just to make that call now |

## Explicitly out of scope for this document

**Document 9:** replenishment order logic — when and how much a store orders, lead times, and what "initial stocking" means for a newly-assorted SKU.

**M2B / Phase 2:** retailer-reported inventory as an actual feed — cadence, staleness direction, fault characteristics.

**Analytical Engine milestone:** the likely-inventory-state inference algorithm.

**Deferred, not scoped:** shrinkage, shelf-execution gaps, and any store-front/backroom split.
