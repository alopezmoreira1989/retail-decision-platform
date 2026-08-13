# Document 1 — Company & Business Context

**Status: Approved.** This is a planning document. Nothing here is final until reviewed and approved — see [README.md](README.md) for the review process. Document 2 (Product Universe) begins only once explicitly started as its own task.

## NovaFoods

**NovaFoods** is the fictional company behind the platform. It is a **consumer packaged goods (CPG / FMCG) manufacturer** of branded food and beverage products, sold through retail chains in the United States and Canada.

NovaFoods is a manufacturer, not a technology company. The Retail Decision Platform is NovaFoods' internal analytical system for understanding how its products are actually performing at retail and for generating recommendations its own commercial teams can act on. Everything simulated in Phase 1 is the reality NovaFoods would want visibility into, if its data were perfect — which is precisely what Phase 2 will later take away.

## The core scope distinction: NovaFoods is not the retailer

This distinction governs everything downstream and is worth stating precisely, since it determines what "sales," "inventory," and "orders" mean throughout the rest of Phase 1:

```text
NovaFoods (manufacturer)
    │  sells products through
    ▼
Retailers (NovaFoods' customers)
    │  operate
    ▼
Stores
    │  sell to
    ▼
Consumers
```

- NovaFoods manufactures and brands the products. It does not own or operate any store.
- Retailers are NovaFoods' *customers* — independent businesses that buy NovaFoods products (wholesale/trade terms) and resell them to consumers through their own stores.
- Everything the platform observes about "what happened" at store level — a consumer buying a product, a shelf running low, a store placing a reorder — is something that happens **inside the retailer's business**, not NovaFoods'. NovaFoods only ever finds out about it through what the retailer reports.

Practically, this means:

- **Sales / POS** (Document 7) = the retailer's record of consumer purchases of NovaFoods products in its stores. It is retailer-observed data about consumer behavior, not something NovaFoods generates.
- **Inventory** (Document 8) = the retailer's on-hand stock of NovaFoods products in its stores (and, depending on the retailer, backroom). It is the retailer's inventory, not NovaFoods' — and, critically, it is **latent**: NovaFoods has no reliable direct feed of it. See [Observability](#observability-what-novafoods-can-and-cannot-see) below.
- **Orders** (Document 9) = replenishment orders the *retailer* places to NovaFoods to restock its own shelves. This is the one point where NovaFoods is a direct party to the transaction, rather than an observer of the retailer's business — which makes Orders the most inherently reliable signal in the system: NovaFoods doesn't need to *observe* its own order book, it just has it.
- **Assortment** (Document 5) = which NovaFoods products a given retailer/store has chosen to carry. This is a retailer decision NovaFoods can influence commercially but does not control.

Even in Phase 1 — where, by definition, there is no data-system corruption yet — this distinction still matters conceptually: Phase 1's "ground truth" is the true state of the retailer's business with respect to NovaFoods products (true consumer demand, true sales, true stock, true orders), not NovaFoods' own internal operations (its factories, its own warehouses, its own production planning). Confirmed as an explicit scope boundary — see [Confirmed decisions](#confirmed-decisions) below.

## Business model

NovaFoods sells through the traditional retail trade channel: it manufactures branded products, sells them wholesale to retailers, and retailers resell them to consumers through physical stores. Revenue to NovaFoods is driven by retailer sell-in (orders placed to NovaFoods), which is in turn driven by retailer sell-out (consumer purchases) and the retailer's own inventory decisions.

## Company scale

**Confirmed: NovaFoods is a large North American CPG company.** Large enough to eventually have:

- multiple product categories and multiple brands (Document 2);
- hundreds to thousands of SKUs, eventually (Document 2);
- dozens of retail customers (Document 3);
- thousands of stores (Document 4);
- a substantial commercial organization (Document 11).

This sets the *ambition level* for later documents — Documents 2–4 don't need to hit these numbers on day one (the project's own incremental-delivery principle in [../ARCHITECTURE.md](../ARCHITECTURE.md#incremental-delivery-principle) still applies: start with a small vertical slice, grow toward this scale), but the simulated company should feel, structurally, like it's built to reach this scale rather than being sized as if it will always stay small.

## Geographic scope

Initial markets: **United States** and **Canada**, per the project's existing conventions (see [../../CLAUDE.md](../../CLAUDE.md)). NovaFoods is **one company**, not two country subsidiaries — but it operates through **country-specific commercial structures**. Confirmed as country-specific:

- commercial teams;
- retailer relationships;
- pricing;
- promotions;
- calendars;
- potentially assortment;
- potentially product availability.

In other words, the *distinction between countries is made at the retailer level*, not by splitting NovaFoods into two businesses: a US retailer relationship and a Canadian retailer relationship are managed, priced, and promoted independently, even though both ultimately roll up to the same company. This is more granular than treating "US/Canada" as just a currency-and-holiday-calendar detail, and it means Document 3 (Retailer Universe) and Document 11 (Commercial Activity) will both need a country dimension baked in structurally, not bolted on.

## Commercial organization (placeholder)

NovaFoods has a commercial/sales organization responsible for managing retailer relationships — the people who would act on the platform's recommendations, organized country-by-country per the above. The **Commercial Agent** entity already referenced in [../DATA_MODEL.md](../DATA_MODEL.md) is a NovaFoods employee (e.g. a retail sales representative or account manager), not a retailer employee — worth stating explicitly here since it was previously ambiguous. The full structure and behavior of this organization (account coverage, visit patterns, how they interact with retailers/stores) is deliberately deferred to Document 11 rather than designed now.

## What "ground truth" means for NovaFoods, concretely

Phase 1 answers one question: **what actually happened in the NovaFoods retail ecosystem**, with no notion yet of how well or badly any retailer's data systems captured it. For example:

```text
A consumer buys a NovaFoods product at a retailer's store
        ↓
The retailer's systems record a sale (true sale)
        ↓
That store's true stock of the product decreases
        ↓
Eventually, the retailer places a replenishment order with NovaFoods
        ↓
NovaFoods delivers; the store's true stock increases
```

Nothing about *retailer feed quality, frequency, or reliability* belongs here — that's Phase 2. Document 1 only establishes who the players are and how they relate; the mechanics of demand, sales, inventory, and orders are designed in their own dedicated documents.

## Observability: what NovaFoods can and cannot see

This is a business fact about the manufacturer–retailer relationship, not a Phase 2 data-quality detail — so it belongs here, even though its full mechanics are designed later (Documents 6–9). **This framework — Latent reality → Observable signals → Inference → Action — is confirmed as a core conceptual pillar of the entire project, not just this document.** Formally propagating it into `docs/ARCHITECTURE.md` / `CLAUDE.md` is left as a dedicated future reconciliation task (see [Note for future reconciliation](#note-for-future-reconciliation) below) — this document is its first, authoritative statement.

| Layer | Examples |
|---|---|
| **Latent reality** (never directly observed by NovaFoods, in any world) | Consumer demand, physical inventory |
| **Observable signals** (what NovaFoods actually receives — Phase 2's RAW output) | POS / sell-out, orders, reported inventory (if provided), assortment, promotions, store/product master, events, commercial-agent visit feedback |
| **Inference** (Decision Platform output, not input) | Expected demand, likely availability, likely inventory state, underperformance, order opportunity |
| **Action** | Commercial recommendation |

The clearest illustration is the two latent quantities that matter most and how the platform has to reconstruct them:

```text
                 ACTUAL WORLD
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
 Consumer demand          Physical inventory
     (latent)                  (latent)
          │                     │
          ▼                     ▼
       POS sales          reported inventory
          │                     │
          └──────────┬──────────┘
                      ▼
                 INFERENCE
                      ▼
              RECOMMENDATION
```

The system isn't doing analytics on clean facts — it's reconstructing partially hidden business state from noisy observations. That's the project's actual problem, restated at the most concrete level yet.

**Physical inventory is latent, not merely an imperfect observable.** It sits in the same tier as consumer demand, not the same tier as POS. Even under a hypothetical "perfect" retailer feed (no Phase 2 degradation at all), NovaFoods still would not have the retailer's true stock figure as a matter of course — that's not how the manufacturer/retailer relationship typically works. When a retailer *does* report an inventory number, it lands in the Observable tier as one more noisy signal, never as ground truth reaching NovaFoods directly.

### Inventory-feed availability is a per-retailer characteristic (confirmed, feeds Document 3)

Whether a retailer reports *any* inventory signal at all is a property of that retailer, not a universal given:

```text
Retailer A
    reported_inventory: true

Retailer B
    reported_inventory: false

Retailer C
    reported_inventory: true
    quality: poor
```

Critically — and this distinction stays absolute — `reported_inventory: true` means *"this retailer provides a reported-inventory signal,"* never *"NovaFoods knows actual inventory."* Even a retailer with `reported_inventory: true` and good `quality` is still only providing an Observable-tier proxy; true physical inventory remains latent regardless. The full retailer profile schema is Document 3's job; this is only the governing principle it must respect.

### Orders: highly reliable observation, but not the same as reliable inference from it (confirmed, feeds Document 9)

Orders are the strongest observable signal in the system, because NovaFoods is the direct counterparty to the transaction, not merely an observer of the retailer's business:

```text
ORDER
Actual order received by NovaFoods
        ↓
Highly reliable observation
        ↓
Historical pattern
        ↓
Inferred ordering behaviour (e.g. "Store X normally orders 20 units every two weeks")
```

The order *record itself* is trustworthy and should not have Phase 2 fault injection applied to it artificially — doing so would unnecessarily weaken one of the strongest signals in the system for no realistic reason. But the *inferred pattern* built on top of that history ("this store's normal cadence is X") is not itself a fact — it's something the analytical system learns, and it must contend with genuine business variability: irregular orders, changing cadence, promotional orders, unusually large orders, stores changing behavior over time, and new stores with little history. This variability is a **business phenomenon (Phase 1), not a data-system error (Phase 2)** — the same business-reality-vs-data-error distinction from [../SIMULATION.md](../SIMULATION.md), applied specifically to orders. Document 9 (Orders / Replenishment) inherits this distinction directly.

### Commercial visits: one event type, multiple purposes (confirmed, feeds Document 11)

Rather than inventing separate visit concepts, a commercial visit is modeled as a single underlying event type carrying multiple possible purposes/signals:

```text
Commercial Visit
    ├── inventory observation
    ├── assortment observation
    ├── promotion observation
    ├── recommendation feedback
    └── other qualitative information
```

The detailed structure (frequency, what triggers a visit, how multiple signals on one visit are recorded) is not decided now — deferred to Document 11.

## Confirmed decisions

Resolved through review — Document 1 is considered **approved**:

| Question | Decision |
|---|---|
| Retail channel | Brick-and-mortar only; no e-commerce/DTC |
| NovaFoods' upstream operations | Entirely out of scope — sales/retail perspective only, orders always fulfilled |
| Country structure | One company, country-specific commercial operations (teams, retailer relationships, pricing, promotions, calendars, potentially assortment/availability) |
| Company scale | Large North American CPG company (multiple categories/brands, thousands of SKUs eventually, dozens of retailers, thousands of stores, substantial commercial org) |
| Commercial Agents | NovaFoods employees, not retailer employees |
| Inventory feed availability | Per-retailer characteristic (Document 3) |
| Actual (physical) inventory | Always latent — never a trustworthy direct read for NovaFoods |
| Reported inventory | Observable, but never ground truth, even when available |
| NovaFoods orders (the record itself) | Highly reliable observable signal — no artificial Phase 2 noise |
| Order patterns / cadence | Inferred from historical orders, not itself a fact |
| Order variability (irregular cadence, promotional spikes, new stores, etc.) | Business reality (Phase 1), not data error (Phase 2) |
| Commercial visits | One event type, multiple purposes |
| Latent → Observable → Inference → Action | Confirmed as a core conceptual framework for the whole project, first stated here |

### Note for future reconciliation

The Latent → Observable → Inference → Action framework, and the order-reliability distinction, both have implications beyond this document — `docs/ARCHITECTURE.md`'s "Detection / inference" section and `docs/DATA_MODEL.md`'s `Inventory position` and `Order` entity descriptions will eventually need to reflect them. Per instruction, that propagation is *not* done in this pass — flagging it here so it isn't lost, to be picked up as its own dedicated reconciliation task later, following the same pattern as the earlier Phase 1/Phase 2 reconciliation.

## Explicitly out of scope for this document

Product hierarchy/catalogue, retailer identities/characteristics, store universe, assortment, demand, sales, inventory, orders, promotions, and commercial-agent behavior are all deferred to their own documents (2–11) and are not addressed here.
