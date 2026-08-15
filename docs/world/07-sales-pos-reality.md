# Document 7 — Sales / POS Reality

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 8 (Inventory) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: how Document 6's Actual Demand becomes Actual Sales via an availability constraint, the granularity and ticket-level boundary for that transformation, and where Actual Sales sits relative to Observed POS (Phase 2) — including why Sales doesn't need the three-way Latent/Observable/Inference treatment Documents 4 and 5 required for their own variables.

Does **not** define: inventory/stock mechanics — depletion, replenishment, lead times (Document 8, and this document has a real, acknowledged forward dependency on it); Observed POS as an actual Phase 2 feed, its cadence, or its fault characteristics (M2B); returns, voids, or transaction/basket-level structure (flagged, deferred); orders (Document 9).

## The central risk, stated first: demand, sales, and observed POS are three different numbers

This is the thing to get right before anything else in this document, per the concern raised when this document was scoped:

```text
Actual Demand = 100
        │  availability constraint (this document)
        ↓
Actual Sales = 60          ← could be lower than demand because the product wasn't sufficiently available
        │  Phase 2 observation (not this document)
        ↓
Observed POS ≈ 60          ← an imperfect report of actual sales, not of demand
```

If a future model ever treated Observed POS as a direct stand-in for Demand, it would misread every availability problem as a demand problem — exactly the outcome the platform exists to avoid. This separation is what lets the eventual analytical engine detect availability issues instead of just reporting low sales. Keeping Actual Demand, Actual Sales, and Observed POS as three distinct, never-collapsed quantities is this document's entire job.

## Where Sales sits — different in kind from Document 4/5's latent variables

Worth being explicit about, since by this point in the series a reader might expect every new concept to get the same three-way Latent/Observable/Inference split `store_scale_class` and `physical_assortment` needed. **Sales doesn't need it, and applying the pattern reflexively here would be a mistake in the other direction.**

The reason those two needed the split: there was a *structural* reason truth and observation could diverge even under a hypothetically perfect feed — retailers classify their own stores by inconsistent criteria; head-office assortment records can diverge from shelf reality. Sales isn't like that. Document 1 already treats "the retailer's systems record a sale" as the canonical example of a Phase 1 ground-truth event, and already places POS/sell-out in the Observable tier alongside orders — not in the Latent tier alongside consumer demand and physical inventory. **Under a hypothetical zero-fault Phase 2 feed, Observed POS would simply equal Actual Sales.** Every real-world gap between them is attributable to ordinary Phase 2 degradation (missing days, aggregation level, latency, duplication) — the fault taxonomy already established project-wide — not to some deeper structural uncertainty Phase 1 needs to model. So: Actual Sales is a normal Phase 1 ground-truth fact, reported to Phase 2 the same way everything else is, no special three-way treatment required.

**Confirmed.** The model simplifies cleanly to:

```text
Consumer Demand
        ↓
Actual Sales
        ↓
Observed POS
```

with no hidden "true sales" state underneath Actual Sales — the Demand→Sales gap is a real availability constraint (this document), and the Sales→Observed POS gap belongs entirely to Phase 2 feed degradation. The check on retailer-specific sale definitions (multi-buys, bundles) was worth raising explicitly rather than silently assumed away, and stays noted rather than dropped: if it later turns out to matter, it's naturally a **Phase 2 semantic transformation** (the same category as Document 2's units-vs-cases distortion), not a reason to reopen Phase 1's definition of Actual Sales.

## Actual Sales: the demand-to-sales transformation

**Proposed:** the standard relationship already implied since the project's earliest planning (`Sales = min(demand, available stock)`), now made precise against Document 6's terms:

```text
Actual Sales(store, sku, day) = min( Actual Demand(store, sku, day), stock available at the start of day )
```

**"Stock available at the start of day" is an external input, not designed in this document.** Document 8 (Inventory) owns everything about how that quantity comes to be — depletion, replenishment, lead times. This document only defines the shape of the relationship demand and stock enter into to produce sales, the same way Document 5 treated `true_stock` as an input owned entirely by Document 8 without needing to resolve it. This is a real, acknowledged forward dependency, not a gap being glossed over: Document 7 comes before Document 8 in the roadmap, but conceptually needs one quantity from it. That's fine as long as the dependency is named, not hidden.

**Confirmed: no partial-fulfillment nuance.** The simple `min()` relationship assumes any available quantity up to demand gets sold — not a claim that real shopper behavior never involves declining a smaller-than-desired quantity, just a deliberate simplification for the initial Ground Truth. The reasoning is worth stating plainly: this document's job is to establish the *fundamental causal relationship*, not to reproduce every operational detail of a real POS system. A more granular model (e.g., splitting an unmet 40 units into "10 lost to shelf-execution gaps, 5 to store rules, 25 to a plain stockout") is a plausible future refinement, but adding it now would make it harder to tell, later, whether a problem in the analytical system traces back to the core inference problem or to unnecessary simulator complexity. `min(demand, stock)` is the correct first-order mechanism precisely because it keeps that distinction clean.

## Granularity and the ticket-level boundary

**Proposed:** Actual Sales is generated at the same granularity as Actual Demand — store × SKU × day, in units. This isn't a new decision; it follows directly from CLAUDE.md's own existing statement: *"Ticket-level transaction generation is a Phase 2 concern — it's about how a POS system captures a day's true sales, not about business reality itself."* Phase 1 produces a daily total; any retailer-specific disaggregation into individual tickets (for retailers whose POS reports at ticket level) is entirely M2B's job, not designed here.

## The acyclicity rule, reaffirmed

Document 6's generalized rule applies without modification: Actual Sales is downstream of Actual Demand, so nothing about Actual Sales — directly or via a derived feature — may feed back into Demand or Potential Demand generation. It extends the same canonical ordering one step further, unchanged:

```text
World / Parameters → Potential Demand → Actual Demand → Actual Sales → Observed POS
```

One addition specific to this document: generating a given day's Actual Sales may depend on stock *entering* that day (itself a consequence of prior days' sales and replenishment, Document 8's ordinary temporal dynamics) — that's a legitimate sequential dependency across time, not a violation of the acyclicity rule, which concerns generation *within* a single causal step, not the normal day-over-day evolution of stock levels.

**Confirmed shape for that temporal dependency, as guidance for Document 8:** rather than treating inventory, demand, and sales as three independently-generated quantities that happen to relate, the natural model is a per-day state transition:

```text
Inventory[t] → Demand[t] → Sales[t] → Inventory[t+1]
```

Stated this way, there's no circularity at all — each day's stock is simply the previous day's state, carried forward and updated by that day's sales (and any replenishment arriving). **Document 8 remains the sole authoritative place for inventory mechanics.** This document deliberately stops at treating "stock available at start of day" as an opaque input precisely so that inventory rules don't get quietly designed piecemeal inside Sales — Document 8 should design the full state-transition mechanism, not inherit fragments of it from here.

## Observed POS — not this document's job, boundary restated

Flagged only, to close the chain cleanly: Observed POS is Phase 2's report of Actual Sales, subject to the project's already-established fault taxonomy (missing days, duplicates, aggregation level, latency — nothing new invented here). Designing that feed is M2B's job. This document's only responsibility toward it is making sure Actual Sales exists as a clean, independent quantity for Phase 2 to degrade — not defining the degradation itself.

## Explicitly deferred: returns, voids, and transaction/basket structure

**Confirmed deferred**, for the initial vertical slice. Real phenomena in actual retail operation, but not modeled in this document: returns (negative sales events), voided transactions, and any transaction- or basket-level structure beyond a daily unit total. Returns specifically raise several genuine questions that aren't central to what this document exists to establish — does a return reverse the original sale, on what date, does inventory increase, is the item resellable, does the retailer report it separately, how are financial returns represented — all interesting eventually, none necessary for the core `Demand → availability constraint → Sales → POS` chain this document is about. Consistent with Document 6's shopper-journey simplification and the project's incremental-delivery principle — a known simplification, not an assumption that returns don't happen in reality.

## Illustrative example (matching the numbers used to scope this document)

Purely to make the transformation concrete — none of this is a real decision:

```text
BayMart Store #118 × RidgeCrest Kettle-Style Sea Salt Chips, 8 oz, US — a Tuesday in March

Actual Demand (Document 6):        100 units
Stock available at start of day (Document 8, not designed here):  60 units
        ↓
Actual Sales = min(100, 60) = 60 units
        ↓
[M2B's job from here: Observed POS ≈ 60, subject to ordinary Phase 2 degradation]
```

The gap between 100 and 60 is a genuine availability problem — the exact kind of situation the platform exists to eventually detect, made possible only because Demand and Sales were never allowed to collapse into the same number.

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Latent/Observable/Inference split for Sales? | No — agreed. Model simplifies to `Consumer Demand → Actual Sales → Observed POS`, with the Sales↔Observed-POS gap attributable entirely to Phase 2 degradation |
| Retailer-specific sale definitions (multi-buys, bundles)? | Noted, not modeled now; a future Phase 2 semantic transformation if it turns out to matter, not a reason to reopen Phase 1's Actual Sales definition |
| `Actual Sales = min(Actual Demand, stock available at start of day)`? | Yes, for the initial Ground Truth — establishes the fundamental causal relationship without reproducing full POS operational detail |
| Partial-fulfillment refusal? | Not modeled — deliberate, to keep it clear later whether analytical-system problems trace to the core inference problem or to unnecessary simulator complexity |
| Granularity | Store × SKU × day; ticket-level generation is M2B's job |
| Returns, voids, basket structure? | Deferred for the initial vertical slice — a known simplification, not an assumption they don't exist |
| Temporal dependency on stock-at-start-of-day | Framed as a per-day state transition (`Inventory[t] → Demand[t] → Sales[t] → Inventory[t+1]`), not circularity; Document 8 remains sole authority on inventory mechanics |

## Explicitly out of scope for this document

**Document 8:** stock available at start of day, and everything about how it comes to be — depletion, replenishment, lead times.

**Document 9:** how sales depletion eventually triggers replenishment orders.

**M2B / Phase 2:** Observed POS as an actual feed — cadence, fault characteristics, ticket-level disaggregation.

**Deferred, not scoped:** returns, voids, transaction/basket-level structure, partial-fulfillment consumer behavior.
