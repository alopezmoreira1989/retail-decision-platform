# Document 2 — Product Universe

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 3 (Retailer Universe) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: the product hierarchy, categories/subcategories, brands, the SKU concept, pack size and case-pack attributes, the canonical units convention, and product lifecycle.

Does **not** define: which stores/retailers actually carry which products (Document 5, Assortment), the literal enumerated catalogue of specific SKUs (an implementation task once this structure is approved, not a planning document), demand or price elasticity (Document 6), or retailer-specific identifiers/category mappings (Document 3 / Phase 2 — retailers may classify or code products differently than NovaFoods does internally; that mismatch is itself a realistic phenomenon, noted below, but not designed here).

## Product hierarchy

A real CPG catalogue isn't a single clean tree — **Category and Brand are two separate, crossed axes**, not nested. A brand commonly spans multiple categories (e.g., a snack brand that makes both chips and crackers), so forcing Brand under Category would misrepresent how the business actually works.

```text
Category
   └── Subcategory
                              Brand   (crossed axis — spans categories freely)
                                 │
                                 ▼
                             Product   (a formulation/flavor/variant, country-agnostic)
                                 │
                                 ▼
                               SKU     (a specific sellable pack size/format, per country)
```

`Product` and `SKU` are deliberately separate levels: a `Product` is "NovaFoods' Kettle-Style Sea Salt Chips" as a concept; a `SKU` is the specific, sellable, country-specific, pack-size-specific item — "NovaFoods Kettle-Style Sea Salt Chips, 8 oz bag, US" vs. "..., 235 g bag, Canada" are two different SKUs of the same Product.

## Category & Subcategory

NovaFoods' own internal categorization — this is Phase 1 canonical truth, i.e., how NovaFoods itself organizes its catalogue. **Flagging, not designing:** real retailers often classify the same products into their own category/aisle taxonomy for shelf planning, which doesn't always match a manufacturer's internal categorization. That mismatch is a genuine, realistic phenomenon (closer to a Document 3/5 or even Phase 2 concern — a retailer-specific "view" of the same product) but is out of scope here; Document 2 only fixes NovaFoods' own canonical structure.

Illustrative only (not a final list):

```text
Category: Salty Snacks
   Subcategory: Potato Chips
   Subcategory: Tortilla Chips
   Subcategory: Pretzels

Category: Beverages
   Subcategory: Sparkling Water
   Subcategory: Juices & Blends
```

## Brand

A NovaFoods-owned label, able to span multiple categories/subcategories. No further holding-company layer is needed — NovaFoods is the only "parent," so `Brand` sits directly under NovaFoods, not under an intermediate portfolio concept.

Illustrative only: a brand called "RidgeCrest" spanning both the Potato Chips and Tortilla Chips subcategories above.

## Product (the base item)

A specific formulation/flavor/variant under a brand, independent of pack size and country. Carries: name, brand, category/subcategory, launch date, an `is_seasonal` flag with an active window (for limited-time items — see [Lifecycle](#product-lifecycle) below), and a lifecycle state that its SKUs can individually override (see below).

## SKU — the sellable unit

The concrete, country-specific, pack-size-specific item — this is the level that carries a barcode/identifier and a price, and the level Phase 1's sales/inventory/orders ultimately operate on.

Proposed SKU attributes:

- pack size / format (e.g., "8 oz bag," "12-pack cans")
- country (US or Canada — see below)
- NovaFoods-internal SKU code (the canonical identifier within Phase 1; retailer-specific identifier *mapping* is a Phase 2/Document 3 concern, not designed here)
- `units_per_case` (see [Units, cases, and the canonical convention](#units-cases-and-the-canonical-convention))
- lifecycle state and dates (a SKU can move through its own lifecycle independently of its parent Product — e.g., the US pack size is discontinued while the Canadian one continues) — see [Product lifecycle](#product-lifecycle)
- price is deliberately *not* a direct SKU attribute — see [Price](#price-scope-note) for why

**Proposed: `Product` is shared across US and Canada; `SKU` is where country-specificity enters.** This matches real CPG practice — packaging, language (bilingual labeling in Canada), and sometimes pack size itself differ by country for what is conceptually the same product — and it lines up with Document 1's confirmed country-specific "potentially product availability" dimension.

## Units, cases, and the canonical convention

This directly resolves the open canonical-semantics question carried over from Document 1 and tracked as its own GitHub issue ("Define Phase 1 canonical semantic and unit conventions"). Proposed resolution:

- **"Units"** = consumer sellable eaches at the SKU level. Whatever a consumer picks up as a single retail item counts as 1 unit, regardless of what's physically inside it — a 12-pack of cans sold as one shelf item is 1 unit if that's how the SKU is defined. This matches how real POS systems actually work: a scan at checkout counts one unit sold, at the SKU/barcode level, not at some other physical measure.
- **`units_per_case`** — a separate, explicit SKU attribute for the manufacturer-to-retailer shipping multiplier (how many consumer units come packed in a case). This is what Document 9 (Orders) will need, since retailers commonly order and receive product in whole-case increments even though they sell in eaches. Keeping this as its own named attribute avoids ever conflating "units" with "cases."
- **Inventory** (Document 8 — though per Document 1, always latent) is proposed to be internally denominated in the same "units" convention as sales, for consistency, even though NovaFoods never gets a trustworthy direct read of it.

If approved, this proposal is intended to close out the "canonical semantic/unit conventions" question flagged as open in `docs/SIMULATION.md` and its tracking issue.

## Product lifecycle

**Confirmed: three states**, not two — two was too simplistic for the world this project is building:

```text
ACTIVE ──────────────► TEMPORARILY_UNAVAILABLE ──────────────► ACTIVE (resumed)
   │                            │
   │                            ▼
   └──────────────────► DISCONTINUED  (terminal — no return)
```

- **ACTIVE** — currently sellable, eligible for assortment/demand.
- **TEMPORARILY_UNAVAILABLE** — a genuine, temporary Phase 1 business state: NovaFoods itself cannot currently supply the product (e.g., a formulation temporarily paused, production temporarily suspended). The product record persists and can return to ACTIVE, or later move to DISCONTINUED if the pause turns out to be permanent.
- **DISCONTINUED** — permanently withdrawn, with a `discontinued_on` date. Terminal.

**Confirmed: Product identity is immutable.** Lifecycle state can progress, but a discontinued Product can never be reactivated. A genuine relaunch of a similar concept creates a *new* Product identity, not a resurrection of the old one — the reason is analytical, not just tidiness: a relaunch isn't necessarily the same commercial product from the perspective of its historical demand, assortment, and lifecycle, and reactivating an old identity would make that historical record ambiguous for every downstream model.

This doesn't preclude relating the two later. A future, *not-built-now* product-master concept could link them explicitly:

```text
Product A                Product B
DISCONTINUED  ── successor_to ──►  ACTIVE
```

Noted here only so the immutability rule doesn't accidentally block a legitimate future need — no `successor_to` relationship is part of this document's scope.

**Critical boundary, stated explicitly because it's easy to get wrong later:** `TEMPORARILY_UNAVAILABLE` must only ever reflect a genuine Phase 1 business event — something that actually happened to the product. It must never be triggered by a Phase 2 data-system problem.

| Phase 1 (changes the lifecycle state) | Phase 2 (never changes the lifecycle state) |
|---|---|
| NovaFoods temporarily suspends production of a formulation | A retailer's feed fails to include the SKU this week |
| A product formulation is temporarily unavailable | A retailer's category mapping drops the SKU |
| NovaFoods permanently discontinues a product | A retailer misreports the SKU as delisted due to a system error |

A SKU can be `ACTIVE` in Phase 1 ground truth for the entire time a specific retailer's Phase 2 feed simply fails to mention it — that's a reporting gap, not a lifecycle change, and the two must never be conflated.

Every Product/SKU also carries an `active_from` date (its launch date). A new product launch is just an `ACTIVE` record whose `active_from` is at or after simulation start — the *demand ramp-up curve* on launch is a Document 6 concern, not this document's. Seasonality remains modeled as an `is_seasonal` flag plus an active date window on an otherwise-`ACTIVE` product (e.g., a limited-time flavor), rather than as a fourth lifecycle state — consistent with "no more than three states at this stage."

## Price (scope note)

**Confirmed: wholesale list price only, for now — but modeled as a time-versioned record, not a static SKU attribute.** This is a deliberate modeling choice: putting price directly on the SKU would make historical price changes impossible to represent without redesigning the model later, so price is instead its own record, keyed by SKU and effective date range:

```text
Price record
    country
    sku
    effective_from
    effective_to      (nullable — open-ended for the current price)
    list_price
    currency           (USD or CAD — kept explicit rather than inferred from country)
```

This is the price NovaFoods charges the retailer — distinct from, and *not* to be confused with, whatever the retailer subsequently negotiates or charges consumers:

```text
NovaFoods
    ↓  wholesale list price   (modeled now)
Retailer
    ↓  negotiated commercial terms / actual purchase price   (NOT modeled — see below)
    ↓  retail shelf price     (Document 6 / Document 10)
Consumer
```

**Confirmed: retailer-specific negotiated pricing and commercial terms are explicitly out of scope**, now and for the foreseeable scope of this project — they add real complexity without being necessary to the platform's central question. Only the single, country-specific wholesale list price (versioned over time) is modeled. Retail shelf pricing, promotional price changes, and price elasticity of demand remain deferred to Document 6 (Demand) and Document 10 (Promotions & Events).

## Illustrative example (not a final catalogue)

Purely to make the abstraction concrete — none of this is a real decision:

```text
Category: Salty Snacks → Subcategory: Potato Chips
Brand: RidgeCrest
  Product: RidgeCrest Kettle-Style Sea Salt Chips
    SKU: 8 oz bag, US        — units_per_case: 12, active
    SKU: 235 g bag, Canada   — units_per_case: 12, active
    SKU: 2 oz bag (single-serve), US — units_per_case: 30, active
  Product: RidgeCrest Kettle-Style Sea Salt Chips, Jalapeño (seasonal)
    SKU: 8 oz bag, US — units_per_case: 12, is_seasonal: true, active window: Apr–Aug
```

## Confirmed decisions

Resolved through review:

| Question | Decision |
|---|---|
| Category vs. Brand structure | Crossed axes, not a strict tree — a brand can span unrelated categories (e.g., Coffee, Cereals, Snacks) |
| NovaFoods' category taxonomy | Its own internal canonical structure; retailer-side classification differences are real but out of scope here |
| Product vs. SKU country-specificity | `Product` shared across US/Canada; `SKU` is country-specific |
| Canonical units | Consumer sellable eaches at the SKU level; `units_per_case` is a separate, explicit attribute |
| Product lifecycle | Three states — `ACTIVE`, `TEMPORARILY_UNAVAILABLE`, `DISCONTINUED` — with `TEMPORARILY_UNAVAILABLE` reserved strictly for genuine Phase 1 business events, never for Phase 2 reporting gaps |
| Product identity | Immutable — `DISCONTINUED` is terminal; a relaunch creates a new Product identity, not a reactivation. A future `successor_to` relationship between Product identities is a plausible later extension, not built now |
| Catalogue scale | Deliberately **not decided now** — deferred until the retailer/store universe (Documents 3–4) is understood, and treated as simulator *configuration*, not a hardcoded constant, once decided |
| Pricing | Wholesale list price only, modeled as a time-versioned record (country, SKU, effective_from/to, list_price, currency), not a static SKU attribute. Retailer-specific negotiated pricing/commercial terms are explicitly out of scope |

## Explicitly out of scope for this document

Actual catalogue generation (specific categories/brands/SKUs beyond illustrative examples), assortment (which stores/retailers carry which SKUs — Document 5), retailer-specific product identifiers and category mappings (Document 3 / Phase 2), demand modeling and price elasticity (Document 6), and promotional mechanics (Document 10).
