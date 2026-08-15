# Document 3 — Retailer Universe

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 4 (Store Universe) begins only once explicitly started as its own task.

## What is a retailer, in the NovaFoods world?

An independent business that buys NovaFoods products (wholesale/trade terms) and resells them to consumers through its own stores, in one country — per Document 1's core scope distinction. NovaFoods does not own or control a retailer; it has a commercial relationship with one. Everything below elaborates this single sentence: how a retailer is classified, how its identity is scoped, and what a NovaFoods–retailer relationship consists of.

## What this document defines (and what it doesn't)

Defines: retailer identity as a Phase 1 business fact, retailer type (channel format), country-scoping of retailer identity, the retailer/NovaFoods commercial relationship, and the one retailer characteristic already earmarked for this document in Document 1 — standing inventory-visibility.

**Correction from the previous revision:** retailer-level "Tier" has been removed. What actually drives expected sales volume and assortment magnitude is store-level, not retailer-level — a single retailer chain can span enormous variance in individual store size and format. That classification belongs to Document 4 (Store Universe), not here. See [Retailer type](#retailer-type-channel-format) below for what remains at the retailer level.

Does **not** define: individual stores or store networks (Document 4), assortment mechanics (Document 5), or — importantly, see below — retailer *feed* characteristics (POS cadence, latency, schema, product/store identifier schemes, data-quality/fault behavior). Those are Phase 2 (M2B) configuration, designed later when Phase 2 is actually built, not part of this Phase 1 business-model track.

## Where this document sits in the Phase 1 / Phase 2 split

Worth addressing head-on, since it was flagged when this document was scoped: "POS cadence" and "identifiers" were mentioned as things this document would eventually cover. Per the architecture already established and confirmed across `CLAUDE.md`, `docs/DATA_MODEL.md`, and `docs/SIMULATION.md`:

> A store's *ownership* (which retailer chain it belongs to) is a Phase 1 business fact. A retailer's *feed characteristics* (frequency, schema, quality) are Phase 2 configuration.

That rule holds here. **The following are Phase 2 concerns and are not designed in this document, no matter how closely related to "the retailer" they feel:** POS/inventory-feed cadence, latency, granularity, completeness, accuracy, historical availability, technical format, and identifier schemes. All of these belong to M2B (Retailer Feed Simulation), a separate milestone, designed once Phase 2 implementation actually begins. Document 3 only establishes *who the retailers are and what their standing business relationship with NovaFoods is*, never *how their systems technically report*. The underlying principle: **the fact that a retailer provides a signal at all is a business fact; the characteristics of that signal are feed characteristics.**

There's exactly one deliberate exception, already agreed in Document 1: **whether a retailer shares any inventory-related signal with vendors at all** was explicitly assigned to this document ("this belongs in Document 3, because it's fundamentally a characteristic of the retailer's information environment"). Confirmed resolution, kept strictly to this one question and no further:

> Does this retailer, as a matter of standing business practice, share any inventory-related signal with vendors?

Nothing more than that yes/no. `shares_inventory_visibility` must never be read as, or extended to encode, any of the following — all of which stay entirely in Phase 2/M2B:

- feed cadence
- latency
- granularity
- identifiers
- completeness
- accuracy
- historical availability
- technical format

And critically, it must never be read as implying NovaFoods knows actual inventory — Document 1 already established that even `reported_inventory: true` never means that. This is a slow-changing fact about the retailer's *posture toward vendors* (does this relationship include any inventory signal at all), not a measure of whether that signal, when present, is any good.

Also worth being explicit: NovaFoods still needs its own canonical identifier for each retailer (parallel to Document 2's "NovaFoods-internal SKU code") — that's a Phase 1 fact and is included below. What's excluded is the retailer's *own* internal identifier schemes and how they map to NovaFoods' — that mapping is Phase 2's "identifier resolution" concern (`docs/DATA_MODEL.md#identifier-resolution`).

## Retailer identity is country-scoped

**Confirmed:** each Retailer entity is scoped to exactly one country. A real-world chain that happens to operate in both the US and Canada is modeled as **two separate Retailer entities** (e.g., "Meridian Grocers – US" and "Meridian Grocers – Canada"), even though they might share a brand identity in-world — not one entity with country-specific sub-relationships. This follows directly from Document 1's confirmed principle that commercial relationships — pricing, promotions, calendars, the relationship itself — are country-specific: NovaFoods' relationship with a chain's US operations and its Canadian operations are commercially independent, so modeling them as one entity would misrepresent how the relationship actually works.

## Retailer type (channel format)

**Confirmed as an initial taxonomy — a working starting set, not an immutable ontology.** It can be revised later if real-world practice or downstream documents (Document 5's assortment mechanics, Document 6's demand patterns) surface a need to split, merge, or add types; nothing about the architecture requires it to be exhaustive or fixed now.

| Type | Description |
|---|---|
| Grocery / Supermarket | Traditional full-line grocery |
| Mass Merchandiser | Large general-merchandise + grocery combo |
| Club / Warehouse | Membership warehouse format |
| Drug / Pharmacy | Drugstore chain |
| Convenience | Gas station / convenience format |
| Discount / Value | Small-box discount retailer |
| Specialty / Natural | Specialty or natural/organic grocery |

No claims about how each type behaves downstream (assortment breadth, basket size, pack-size preference, etc.) are made here — that would be inventing content not established by any prior document. Type is a classification only; its downstream effects, if any, are for Document 5/6 to establish on their own terms.

## Retailer-level "Tier" was removed — corrected to store-level

An earlier revision of this document proposed a retailer-level Tier (National/Strategic, Regional, Small/Independent), justified partly by "reflecting store count" and implying broader assortment for higher tiers. **That's the wrong level of granularity.** A single retailer chain can contain enormous variance across its own store fleet — a flagship location and a small-format location of the *same* chain don't have comparable sales volume or assortment capacity. Collapsing that into one retailer-level attribute would misrepresent the thing that actually matters.

**Corrected:** whatever classification drives expected sales volume and assortment magnitude belongs at the **store level** — Document 4's job, not this document's. Document 3 makes no claim about retailer size beyond the aggregate, order-of-magnitude store count already noted below; it does not attempt to capture volume or assortment-driving classification at the retailer level at all.

This doesn't rule out NovaFoods still having *some* retailer-level commercial-relationship concept (e.g., which accounts get dedicated coverage) — but that's Document 11's territory if and when it's actually needed there, not something to pre-empt here under a different name.

## Retailer business attributes (Phase 1 facts)

Proposed attribute set for a Retailer entity:

- `retailer_id` — NovaFoods-internal canonical identifier (Phase 1 fact; parallel to Document 2's NovaFoods-internal SKU code)
- `name` — fictional retailer name
- `country` — US or Canada (see [country-scoping](#retailer-identity-is-country-scoped) above)
- `type` — channel format, from the table above
- approximate store count — an aggregate fact about the retailer only (not a store-level model, which is Document 4's job); order of magnitude, exact roster/count deferred, same as catalogue scale in Document 2, until this and Document 4 are both understood together
- `relationship_start` and `relationship_end` (nullable) — see next section
- `shares_inventory_visibility` (boolean) — the standing business characteristic defined above under [Where this document sits](#where-this-document-sits-in-the-phase-1--phase-2-split); nothing more than that yes/no

## The NovaFoods relationship

**Confirmed: a simple date range** — `relationship_start`, and a nullable `relationship_end` for when a relationship ends. No `PAUSED` (or any other intermediate) state is introduced, because none has been demonstrated as a real business requirement. This is a deliberate decision, not an oversight: Document 2's three-state product lifecycle exists because products move through *distinguishable* intermediate conditions that matter to the business (temporarily unavailable is meaningfully different from discontinued); a lifecycle state machine isn't owed to the Retailer entity just because Document 2 happened to need one for Product. If a genuine business need for an intermediate state (e.g., a relationship on hold without being over) surfaces later, it can be added then — not speculated into existence now.

**A NovaFoods retail relationship starting or ending is a genuine Phase 1 business event** — "NovaFoods gains a new retail customer" or "a retailer relationship ends" — analogous to a product being discontinued. It is not a Phase 2 phenomenon and must never be confused with, say, a retailer's feed going silent (which would be a Phase 2 event that doesn't touch this date at all).

The day-to-day mechanics of the relationship (account coverage, visit cadence, who at NovaFoods owns the account) are deliberately deferred to Document 11, per the same pattern as Document 1's placeholder Commercial Organization section.

## Illustrative example (not a final roster)

Purely to make the abstraction concrete — none of this is a real decision:

```text
Meridian Grocers – US        | Grocery        | shares_inventory_visibility: true
Meridian Grocers – Canada    | Grocery        | shares_inventory_visibility: false
BayMart                      | Mass Merch.    | shares_inventory_visibility: true
ClubWest                     | Club/Warehouse | shares_inventory_visibility: false
QuickStop                    | Convenience    | shares_inventory_visibility: false
GreenLeaf Market             | Specialty      | shares_inventory_visibility: false
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Retailer feed characteristics (cadence, latency, granularity, identifiers, completeness, accuracy, historical availability, technical format) | Explicitly out of scope — Phase 2 / M2B, never this document, regardless of how retailer-related they feel |
| `shares_inventory_visibility` | A stable business-relationship trait — "does this retailer, as standing practice, share any inventory-related signal with vendors" — and nothing more; never implies NovaFoods knows actual inventory, never encodes any feed characteristic |
| Retailer identity country-scoping | Country-scoped; a chain in both US and Canada is two Retailer entities, not one entity with country-specific sub-relationships |
| Retailer Type list | An initial taxonomy (Grocery, Mass, Club, Drug, Convenience, Discount, Specialty), not an immutable ontology — revisable later without architectural objection |
| Retailer-level "Tier" | **Removed.** Sales-volume/assortment-magnitude classification belongs at the store level (Document 4), not the retailer level — a single chain's stores vary too much for one retailer-level attribute to represent it meaningfully |
| NovaFoods relationship lifecycle | Simple date range (`relationship_start`, `relationship_end`); no `PAUSED` state without a demonstrated business requirement, and no obligation to mirror Document 2's lifecycle model |
| `shares_inventory_visibility` granularity | Retailer-level only in this document; no store-level exceptions here — if ever needed, that belongs to Document 4 |
| Exact retailer roster/count | Deferred, consistent with Document 2's deferred catalogue scale, until store universe (Document 4) is also understood |

## Assumptions not established by Documents 1–2 (flagged, not invented as fact)

Per the instruction to flag rather than invent: these go a step beyond what Documents 1–2 explicitly settle, kept visible rather than silently assumed.

- **`retailer_id` as a NovaFoods-internal canonical identifier.** Extended by analogy to Document 2's NovaFoods-internal SKU code, not something Document 1 explicitly required for retailers. Reasonable given the established pattern, but noted as an extension rather than a directly-cited rule.
- **Approximate store count as a retailer-level attribute.** Consistent with Document 1's "thousands of stores" scale ambition and Document 2's deferred-scale precedent, but the actual mechanism (a range? an order-of-magnitude label? left blank until Document 4?) isn't decided.

None of these block approval — they're implementation-detail-level or Document 4-adjacent judgment calls, not architectural conflicts.

## Explicitly out of scope for this document

**Document 4:** individual stores, store geography, store-level formats, any store-level exception to `shares_inventory_visibility` should one ever prove necessary, and — most importantly for this revision — the store-level classification that actually drives expected sales volume and assortment magnitude (what a retailer-level "Tier" was standing in for, incorrectly, in the previous revision of this document).

**Document 5:** assortment — which retailers/stores actually carry which SKUs.

**Document 6 / Document 10:** demand, promotions, and pricing dynamics.

**M2B / Phase 2, not any future D3 revision:** POS and inventory-feed cadence, latency, granularity, completeness, accuracy, historical availability, technical format, and retailer-side identifier schemes. These are feed characteristics, not business facts, and belong to Phase 2 regardless of how naturally they might seem to attach to "the retailer."
