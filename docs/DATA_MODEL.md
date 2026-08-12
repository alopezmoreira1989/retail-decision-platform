# Data Model (Conceptual)

This document describes the platform's conceptual entities and relationships. It is deliberately not a finalized schema — table definitions, column names, and types will be established during Milestones M2A–M4 as the simulator and Silver layer are implemented. Treat this as the shared vocabulary for the project, not a migration script.

Several entities here span the Phase 1 / Phase 2 boundary described in [SIMULATION.md](SIMULATION.md): a business fact belongs to Phase 1, while how that fact is reported (or misreported) by a given retailer's systems belongs to Phase 2. This is called out explicitly wherever it applies — see [Retailer configuration](#retailer-configuration) for the clearest example.

## Core entities

- **Country** — a market the platform operates in (initially US, Canada). Carries currency, calendar/holiday context, and regional structure. Phase 1.
- **Retailer** — a fictional retail chain operating in one or more countries. As a Phase 1 entity, carries only business facts (name, country, banner, store roster). Its *feed profile* — frequency, schema quirks, identifier scheme, typical data-quality characteristics — is a separate, Phase 2 concept; see [Retailer configuration](#retailer-configuration).
- **Store** — a physical location belonging to a retailer, located in a country/region. Carries format, size, and regional attributes that influence demand. Phase 1. Store *ownership* (which retailer it belongs to) is a Phase 1 fact even though that retailer's *reporting behavior* is Phase 2 — see [Retailer configuration](#retailer-configuration).
- **Brand** — a fictional manufacturer brand.
- **Category** — a product category/hierarchy node.
- **Product** — a sellable item, belonging to a brand and category. Identifiers may differ by retailer (see [Identifier resolution](#identifier-resolution)).
- **Assortment** — the set of products a given store is expected to carry, which may be inferred rather than authoritatively known.
- **Promotion** — a time-bound price/visibility intervention on a product (or set of products) at a store or retailer level.
- **Calendar / Event** — dates, holidays, and other temporal markers (e.g. regional events) that affect demand.
- **Sale (POS / sell-out)** — an observed unit of sales activity: ticket-level, daily, or weekly aggregate depending on retailer.
- **Order** — a replenishment order placed for a store/product.
- **Inventory position** — reported stock on hand for a store/product at a point in time.
- **Commercial Agent** — a fictional person who reviews recommendations and may visit stores.
- **Store Visit** — a recorded (simulated) visit by a commercial agent, which may itself be a source of ground-truth-adjacent signal or of feedback.
- **Recommendation** — a generated, prioritized, explainable output of the platform, tied to one or more underlying findings.
- **Feedback** — a commercial agent's response to a recommendation.

## Relationships (conceptual)

```text
Country 1───* Retailer 1───* Store
Retailer 1───* Product Identifier Mapping *───1 Product
Brand 1───* Product *───1 Category
Store *───* Product  (via Assortment / observed Sale / Inventory)
Store 1───* Sale *───1 Product
Store 1───* Inventory Position *───1 Product
Store 1───* Order *───1 Product
Retailer/Store/Product *───* Promotion
Store 1───* Store Visit ───1 Commercial Agent
Finding *───1..* → Recommendation
Recommendation 1───* Feedback
```

Exact cardinalities and whether relationships are enforced at the Silver layer or only inferred will be refined once real generation logic exists.

## Retailer configuration

A retailer is split across two layers, matching the Phase 1 / Phase 2 boundary in [SIMULATION.md](SIMULATION.md):

- **Phase 1 — Retailer (business fact).** Name, country, banner, and the set of stores it owns. This is simulated business reality and carries no notion of feeds, schemas, or data quality.
- **Phase 2 — Retailer feed profile (config).** A separate, config-driven object (defined in `config/`) referencing a Phase 1 retailer by ID and describing how *that retailer's systems* report data:
  - reporting frequency per feed (daily, weekly, delayed-by-N-days)
  - identifier scheme (internal SKU vs. EAN/UPC, internal store code vs. address-based)
  - aggregation level (ticket-level vs. daily vs. weekly sell-out)
  - typical data-quality issues and their rates (missingness, duplication, mapping errors)
  - which feeds are provided at all (e.g. a retailer that never sends promotion data)

Keeping these separate means a retailer's business identity never becomes coupled to the implementation details of how its data happens to be delivered — a retailer could, hypothetically, improve its feed quality over time without becoming a "different" retailer in Phase 1. It also keeps retailer variety a matter of configuration, so new retailer archetypes can be added without new code paths. The exact schema for the Phase 2 feed profile is an **M2B (Phase 2 — Retailer Feed Simulation)** deliverable.

## Identifier resolution

Because retailers are expected to use different product and store identifiers, Silver introduces canonical `product_key` / `store_key` concepts, with a mapping layer resolving retailer-local identifiers to them. This mapping is itself subject to data-quality issues (e.g. temporary mismatches after a retailer's own system migration) and is treated as a first-class, versioned artifact rather than a static lookup table.

## Findings and Recommendations schema (preview)

Detection models emit **findings**: a structured statement like "store X, product Y, as of date D, likely out of stock, confidence C, based on evidence E." The recommendation engine consumes findings (possibly several, possibly from different models) and produces **recommendations**: findings translated into a suggested action, deduplicated, and scored for priority. The precise schema is a Milestone 6 deliverable; see [ARCHITECTURE.md](ARCHITECTURE.md#recommendation-engine).

## What is intentionally not defined yet

- Physical table schemas and column-level types for Bronze/Silver/Gold
- The exact statistical/ML feature set
- The precise recommendation priority formula
- The feedback taxonomy's full enumeration (a working set is sketched in the project brief; final set is a Milestone 7 deliverable)

These are left open so they can be designed against real generation and ingestion code rather than guessed upfront.
