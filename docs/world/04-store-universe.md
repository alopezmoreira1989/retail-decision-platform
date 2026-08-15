# Document 4 — Store Universe

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 5 (Assortment) begins only once explicitly started as its own task.

## What this document defines (and what it doesn't)

Defines: individual stores as Phase 1 entities, the retailer/store hierarchy, store geography, store format, store lifecycle, and — the key handoff from Document 3 — the store-level classification that drives expected sales volume and assortment magnitude.

Does **not** define: assortment mechanics (which SKUs a store actually carries — Document 5), demand mechanics (how store classification and other factors mechanically produce actual generated demand numbers — Document 6), or Phase 2 feed characteristics for store/inventory data (cadence, latency, identifiers, reconciliation logic — M2B and, where it becomes an inference problem, the Analytical Engine milestone).

## A note on Phase 1 structure vs. the "no hardcoded rules" analytical principle

Worth stating once, since this document introduces attributes that mechanically shape simulated outcomes: Phase 1's generative machinery is allowed to have deterministic, structural relationships (e.g., a store's true scale influencing the demand Document 6 generates for it) — that's simply what it takes to build a coherent world. The project's "don't hardcode expected behavior" principle governs the Decision Platform's *inference* layer, which never has access to Phase 1 internals in the first place (the hard boundary already established). A Phase 1 structural attribute is not a hardcoded analytical rule; it's the ground truth the analytical layer has to work without.

## What is a store, and how does it relate to its retailer?

A store belongs to exactly one Retailer — a plain one-to-many relationship (Retailer → Stores). Since Retailer identity is already country-scoped (Document 3), a store's country is inherited transitively through its retailer and is not a separate store-level attribute.

## Store master data is retailer-reported (narratively), Phase 1-generated (mechanically)

Worth stating explicitly, because it shapes how the rest of this document should be read: in the fiction of the simulated world, NovaFoods doesn't independently discover that a store exists — a retailer's own systems are the source of a store list (location, maybe GPS coordinates, format, and any classification the retailer applies) that gets sent to NovaFoods, the same way Document 1 already places "store/product master" under the Observable tier. Mechanically, of course, Phase 1 is what actually generates this data, since Phase 1 is the ground-truth author of the whole simulated world. That's not a contradiction: Phase 1 produces the true store universe; the *narrative frame* for how that data would reach NovaFoods is "retailer-reported," consistent with everything already established about Phase 2 being the retailer-shaped observation of Phase 1 reality.

This framing matters most for the next section.

## Store classification: extending the Latent → Observable → Inference framework

Document 3 handed off a specific problem here: the concept that drives expected sales volume and assortment magnitude. The first draft of this section treated that as a simple Phase 1 store attribute. **Reconsidered, based on a real point about how this would actually work**: different retailers classify their own stores by their own inconsistent criteria (a "Tier 1" store at one retailer isn't defined the same way as a "Tier 1" store at another). That's not a minor detail — it means store classification has the same shape as physical inventory in Document 1's framework, not the same shape as, say, a SKU's pack size.

**Confirmed resolution — three distinct concepts, not one:**

- **`store_scale_class`** (Phase 1, **Latent**) — see below; not the same thing this section originally called `true_volume_class`.
- **Retailer-reported store tier** (Phase 2, **Observable** — flagged here, not designed here) — each retailer may report its *own* native classification for its stores, using its own criteria, as part of its store master feed. Like reported inventory, this is a noisy, retailer-specific proxy, not the truth, and different retailers' tiers aren't directly comparable to each other.
- **A NovaFoods-universalized store classification** (**Inference**, not Phase 1 at all) — reconciling inconsistent retailer-reported tiers (plus whatever else is observable — actual sell-through, assortment breadth) into one cross-retailer-comparable measure is an analytical/inference problem for the Decision Platform to solve, not something Phase 1 hands over for free. This belongs to the Analytical Engine milestone, not this document.

This is a direct extension of Document 1's Latent/Observable/Inference table into a domain it didn't originally name (Document 1 listed "consumer demand, physical inventory" as the latent pair — store classification wasn't explicitly called out). The three-way split itself is confirmed.

### `true_volume_class` was circular — corrected to `store_scale_class`

The first revision's name was the actual problem, not just cosmetics. If the latent variable is called a "volume class" and Document 6 then uses it to generate demand, the model quietly becomes:

```text
true_volume_class → demand → sales
```

which reads as *defining* volume by the sales it's supposed to explain — circular. **Corrected: the latent variable is renamed `store_scale_class`** (`store_potential_class` is an equally valid name, if preferred), and redefined as a composite of *structural* characteristics that exist independently of any sales outcome:

- physical capacity and selling space
- customer traffic potential
- catchment area
- number of checkouts
- location
- store format (see below — format is one *input* to scale, not the same attribute)

None of these are observed sales. The causal chain is one-way and non-circular:

```text
store_scale_class → potential demand → actual demand → sales
```

Document 6 (Demand) will define exactly how `store_scale_class` translates into a demand baseline — this document only establishes that the variable exists, what kind of thing it represents (structural potential, not an observed outcome), and the causal direction it must respect.

**Non-determinism, flagged now for Document 6 to respect later:** whatever the eventual demand-generation mechanics turn out to be, `store_scale_class` must **not** map deterministically to demand — e.g., Tier 4 must not simply mean "exactly 4× Tier 1's demand." Substantial variation within each class is required. Otherwise the Decision Platform's analytical models would trivially rediscover the hidden variable directly from observed sales, defeating the entire point of treating it as latent and requiring genuine inference.

**What this means for Document 4's actual scope:** only `store_scale_class` is designed here, as a Phase 1 (Store entity) attribute. The retailer-reported tier and the reconciliation/universalization logic remain explicitly *not* designed in this document — flagged for M2B (the feed) and the Analytical Engine milestone (the reconciliation), respectively.

Proposed illustrative scale (four tiers, confirmed): either framing works and both are offered rather than picking one —

```text
1 — Small / Very Low
2 — Medium / Low
3 — Large / High
4 — Very Large / Very High
```

Per the original framing, this single classification is proposed to drive *both* potential demand (Document 6) and assortment magnitude (Document 5) — the exact mechanics of each are those documents' job, not this one's.

## Geography

Proposed, consistent with store master data being retailer-reported: each store carries a street address, city, state/province, and GPS coordinates (latitude/longitude) — a realistic level of detail for what a retailer's store list would actually contain, and useful groundwork for Document 6's regional-effects modeling. An optional, coarser `region` grouping (e.g., a small set of NovaFoods-defined regions, derived from state/province) is proposed for aggregation/reporting convenience. Not designing anything finer than this (e.g., trade areas, urban/rural classification) — that can be added later if Document 6 actually needs it.

Unlike store classification, geography doesn't need a Latent/Observable split: a store's physical location isn't the kind of quantity that's inherently hard to observe or reported inconsistently across retailers the way a self-defined "tier" is — it's just master data.

## Store format (channel type) — corrected from a size taxonomy

The first revision's `format` list — Small/Compact, Standard, Large/Flagship — was actually describing physical **scale**, not format, and has been absorbed into `store_scale_class` above rather than kept as a separate attribute. **Corrected: `format` is a genuine channel-type taxonomy**, proposed as an initial taxonomy in the same spirit as Document 3's Retailer Type list — a working starting set, not fixed:

| Format | Description |
|---|---|
| Supermarket | Full-line grocery format |
| Hypermarket | Large-format grocery + general merchandise |
| Convenience | Small-format, convenience-oriented |
| Discount | Value-oriented, limited-assortment format |
| Wholesale | Club/warehouse-style format |
| Specialty | Curated or category-focused format |

Format is correlated with, but not identical to, `store_scale_class` — a Hypermarket-format location isn't automatically the highest-scale store (a well-located Supermarket can outperform a poorly-sited Hypermarket), and format is only one of several inputs that contribute to scale, not scale itself. This also means Format can genuinely diverge from the store's own Retailer's Type (Document 3): a retailer classified as Mass Merchandiser at the chain level could still operate some Hypermarket-format locations alongside smaller-format ones — chain-level categorization and individual-location format are related but distinct.

## Store lifecycle

**Proposed: three states — `OPEN`, `TEMPORARILY_CLOSED`, `CLOSED`.** This is *not* a reflexive copy of Document 2's product lifecycle, and it's worth explaining why it's justified here when Document 3 explicitly rejected adding a `PAUSED` state for retailer relationships: store renovations, natural disasters, and other temporary closures are a common, well-known real-world phenomenon with no equivalent at the retailer-relationship level — there's a demonstrated business reason for the middle state here that wasn't present in Document 3's case.

```text
OPEN ──────────────► TEMPORARILY_CLOSED ──────────────► OPEN (reopened)
  │                          │
  │                          ▼
  └──────────────────► CLOSED  (terminal)
```

Same Phase 1/Phase 2 boundary discipline as Document 2's product lifecycle:

| Phase 1 (changes the lifecycle state) | Phase 2 (never changes the lifecycle state) |
|---|---|
| Store closes temporarily for renovation | A retailer's feed fails to include the store this week |
| Store is damaged/closed by a disaster | A retailer misreports the store as closed due to a system error |
| Store permanently closes | A retailer's store master feed is late or incomplete |

**Store identity continuity differs from Product's, and deliberately so.** Document 2 made `DISCONTINUED` terminal for Product, with a relaunch always becoming a new Product identity, for analytical-history reasons. Stores are different: a store that reopens after `TEMPORARILY_CLOSED` **retains its identity** — this is what real retail "comparable store sales" (same-store sales) analysis depends on, and breaking continuity on every renovation would make that kind of analysis impossible to represent. `CLOSED`, however, is terminal, the same way `DISCONTINUED` is for Product: a new store opening later, even at the same address, is a new Store identity.

## Store attributes (Phase 1 facts)

Proposed attribute set for a Store entity:

- `store_id` — NovaFoods-internal canonical identifier (same pattern as `retailer_id` and Document 2's SKU code)
- `retailer_id` — FK to Retailer (country and NovaFoods-relationship dates are inherited transitively, not duplicated here)
- `address`, `city`, `state_province`, `latitude`/`longitude`
- `region` (optional, derived grouping)
- `format` — channel type: Supermarket, Hypermarket, Convenience, Discount, Wholesale, or Specialty
- `store_scale_class` — Phase 1 latent ground truth, a composite structural characteristic (see above); never exposed directly to the Decision Platform, and never defined in terms of sales/demand
- `open_date`
- lifecycle state (`OPEN` / `TEMPORARILY_CLOSED` / `CLOSED`) and `closed_date` (nullable, set only on permanent closure)

**Explicitly not introduced:** a store-level override for `shares_inventory_visibility`. Document 3 established that attribute at the retailer level by default, with a store-level exception deferred to this document only if genuinely justified. Nothing here justifies one yet, so none is added — consistent with not inventing complexity ahead of a demonstrated need.

## Illustrative example (not a final roster)

Purely to make the abstraction concrete — none of this is a real decision:

```text
Meridian Grocers – US, Store #4021
  Springfield, IL | Supermarket format | store_scale_class: 2 (Medium) | OPEN

BayMart, Store #118
  Round Rock, TX | Hypermarket format | store_scale_class: 4 (Very Large) | OPEN

ClubWest, Store #009
  Kelowna, BC | Wholesale format | store_scale_class: 4 (Very Large) | TEMPORARILY_CLOSED (renovation)
```

## Confirmed decisions

Resolved through two rounds of review:

| Question | Decision |
|---|---|
| Latent / Observable / Inferred store classification (three-way split) | Confirmed |
| Latent variable naming | `true_volume_class` was circular (defined by the sales it explains) — corrected to `store_scale_class`, a composite of structural characteristics (physical capacity, traffic potential, catchment area, checkouts, location, format), causally upstream of demand, never derived from it |
| `store_scale_class` drives both potential demand and assortment magnitude | Confirmed — mechanics deferred to Documents 6 and 5 respectively |
| Non-determinism | Confirmed requirement: no deterministic mapping from `store_scale_class` to demand (e.g., Tier 4 ≠ exactly 4× Tier 1) — substantial within-class variation required so the variable isn't trivially rediscoverable from observed sales |
| Four-tier illustrative scale | Confirmed |
| Geography includes GPS coordinates | Confirmed — ordinary Observable master data, no latent/reported split needed |
| Store lifecycle: three states | Confirmed |
| Store identity survives `TEMPORARILY_CLOSED` → reopening | Confirmed (same-store-sales continuity); only `CLOSED` is terminal |
| `format` | Corrected — the original Small/Compact/Standard/Large-Flagship list was actually describing scale, not format. Genuine format taxonomy (Supermarket, Hypermarket, Convenience, Discount, Wholesale, Specialty) now kept separate from, and correlated with but not identical to, `store_scale_class` |
| Store-level `shares_inventory_visibility` override | Not introduced |

## Explicitly out of scope for this document

Assortment mechanics — how `store_scale_class` translates into actual SKU counts (Document 5). Demand mechanics — how `store_scale_class` and geography translate into actual generated demand numbers, and the non-deterministic within-class variation required (Document 6). Retailer-reported store tier as a Phase 2 feed, and its reconciliation into a NovaFoods-universalized classification (M2B and the Analytical Engine milestone, respectively) — flagged here, designed there. Any store-level `shares_inventory_visibility` exception (not introduced; Document 3's retailer-level default stands).
