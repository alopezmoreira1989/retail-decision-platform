# Simulation Philosophy

This document explains what the simulator represents and why it's split into two phases. It works alongside [../CLAUDE.md](../CLAUDE.md), which states the two-phase model as a binding architectural constraint — this document is the fuller explanation of the reasoning; CLAUDE.md is the authoritative summary if the two ever drift.

## Why simulate a whole world instead of generating a dataset

A single, static synthetic dataset would let the project *demonstrate* analytics code, but not *evaluate* it. If there is no notion of what actually happened in a store, there is no way to know whether an "out of stock" recommendation was right. The platform instead simulates a small retail economy with an internal, coherent notion of ground truth, and then generates *observations* of that economy the way real retailers would report them — imperfectly.

This split is what allows the project to ask, and actually answer, questions like: *How much does recommendation accuracy degrade when POS data is weekly instead of daily? Does a peer-based expected-sales model outperform a fixed-cluster baseline? How much does human feedback improve precision over time?*

## Two phases, not two flavors of the same generator

Earlier drafts of this document described a single simulator producing a "hidden state" and "observable data" as two views of one generation process. That framing undersold an important distinction, and the project now treats simulation as **two separate phases with different responsibilities, different allowed content, and a one-way dependency between them.**

### Phase 1 — Retail World / Ground Truth

Phase 1 is simulated **business reality**. It generates a coherent, internally consistent retail world: stores, products, demand, sales, inventory, orders, assortment, promotions, launches, seasonality, holidays, regional effects, and commercial activity. Relationships are causal, not independently random:

```text
Customer demand
       ↓
Actual sales (capped by actual availability)
       ↓
Actual inventory decreases
       ↓
Replenishment order
       ↓
Delivery
       ↓
Actual inventory increases
```

Phase 1 **may** contain genuine business phenomena: a product genuinely goes out of stock, demand genuinely spikes, a store genuinely stops selling a product, a promotion genuinely lifts demand, a product is genuinely discontinued.

Phase 1 **must not** contain data-system corruption of any kind — no missing/duplicated rows, no broken identifiers, no delayed feeds, no malformed schemas, no ETL failures, no synchronization errors. Phase 1 has no concept of "retailer profile," "feed," "schema," or "fault." It doesn't know it is being observed.

Phase 1 reports everything in one fixed, canonical semantic and unit convention (see [Canonical semantics](#canonical-semantics-resolved)) at a time resolution fine enough to support whatever Phase 2 later needs to aggregate or disaggregate.

### Phase 2 — Retailer Feed Simulation

Phase 2 consumes Phase 1's output — and only Phase 1's output, through a narrow read interface, never Phase 1's internals — and simulates what an external retailer's systems would actually transmit. This is where data imperfections are introduced. The result is a **source artifact** — a CSV, an XLSX, a database-like read, whatever a given retailer's systems would actually hand over — which, once landed and ingested, becomes **RAW**: the only representation of a retailer's data the rest of the platform (ingestion, Bronze, Silver, Gold, analytics, recommendations) is ever allowed to read. See [Source artifacts, delivery mechanism, and landing](#source-artifacts-delivery-mechanism-and-landing) below for what sits between a source artifact and RAW.

> Phase 1 represents reality. Phase 2 represents what the data systems tell us about reality.

Phase 2 varies by retailer, driven by a **configurable retailer feed profile**, not hardcoded per-retailer branches: schema, frequency, latency, identifiers, aggregation level (ticket-level vs. daily vs. weekly), delivery mechanism and format (see below), and data-quality/maturity characteristics.

Phase 2 may introduce: missing records, duplicates, delayed or partial feeds, stale inventory, identifier mismatches, schema changes, incorrect mappings, missing promotions, aggregation differences, semantic distortions, temporary system failures, and historical corrections. Wherever practical, these have a simulated **operational cause** rather than being arbitrary noise:

```text
POS system migration at a retailer
    → temporary product/store identifier mismatch for N days
    → affected sales appear to "disappear" from the canonical view until mapping is fixed

ETL job failure at a retailer's data warehouse
    → one or more days of sales missing entirely for that retailer
    → often clustered (e.g. a Sunday batch job silently fails repeatedly)

Inventory synchronization delay
    → reported stock lags true stock by hours/days
    → stock appears higher than reality right after a sales spike (understated depletion)

Historical correction
    → a retailer resends a corrected prior period
    → downstream Bronze/Silver must handle late-arriving, revised history
```

Modeling *causes* rather than raw noise rates makes the resulting data-quality issues internally consistent (a migration affects a contiguous identifier range and a contiguous time window, not random unrelated rows) — more realistic, and more useful for testing robustness.

**Scope-bleed rule:** Phase 2 may only change *how* a Phase 1 event is observed or reported. It may never invent a new business event. If a piece of logic seems to require Phase 2 to "decide" that something happened in the world, that logic belongs in Phase 1 instead.

## Source artifacts, delivery mechanism, and landing

Phase 2's output is not RAW by itself — it is a **source artifact**: the concrete file, API response, or database read that a given retailer's systems would actually hand over. Between that artifact and RAW (the first thing the Decision Platform is allowed to read) sit two more layers, kept deliberately distinct rather than collapsed into one "data source" concept:

```text
Phase 2 (Retailer Feed Simulation)
        ↓ produces
Source artifact         — a CSV, an XLSX, a DB-like read: what the retailer's systems hand over
        ↓ via a delivery mechanism (file drop, API-like, DB-like — retailer-profile-specific)
Landing / exchange       — e.g. a file-exchange endpoint for file-based feeds; other endpoints for other mechanisms
        ↓ ingested
RAW
```

**Which delivery mechanism and format a retailer profile plausibly uses is a Phase 2 characteristic** — the same category as schema, frequency, latency, identifiers, and aggregation level, already established above. Phase 2 decides and simulates *what* the artifact would look like and *which* mechanism a given retailer would plausibly use; it does not operate real infrastructure. Actually placing an artifact at a landing/exchange endpoint, and pulling it from there into the warehouse, is ingestion-adjacent tooling — outside both Phase 1 and Phase 2, and outside this document's scope. See [ARCHITECTURE.md](ARCHITECTURE.md#source-artifact-delivery-mechanism-and-landing) for where this sits in the fuller data flow.

**Format plurality, deliberately not narrowed to one:** the simulator should model plausible delivery patterns, not reproduce a single canonical enterprise technology stack. A retailer profile's format is one of several plausible choices, picked per profile, not fixed project-wide:

- **XLSX** — master/reference data, small periodic feeds (assortment, price lists). Not viable at real POS volume — Excel's roughly 1,048,576-row-per-worksheet ceiling makes it unsuitable for anything beyond a small, low-cardinality feed.
- **CSV / flat files** — the primary format for large file-based feeds (typical for POS at real volume).
- **Parquet** — a plausible, if less common, delivery format for a retailer profile representing a more modern/analytics-oriented integration. Not the default, not excluded.
- **API-like** — a structured, on-demand integration.
- **DB-like** — a direct table/read-replica-style integration.

**Ticket-level POS is a Phase 2 representation choice, never a Phase 1 resolution.** Phase 1's Sales stays at store × SKU × day (see [Canonical semantics](#canonical-semantics-resolved)) regardless of what any retailer profile reports. A profile whose aggregation level is ticket-level is Phase 2 disaggregating that same daily total into individual transactions the way that retailer's POS would actually report them — the ingestion/Silver layer is responsible for correctly re-aggregating ticket-level feeds back to store × SKU × day, the same canonical grain every other profile already reports at. This isn't a new phenomenon — CLAUDE.md and `docs/world/07-sales-pos-reality.md` already named ticket-level generation as "a Phase 2 concern... not about business reality itself"; this section just gives it an explicit place now that delivery mechanism is part of the picture. In practice, ticket-level generation is expected to be used for at most one or two illustrative retailer profiles, scoped to a small store/SKU/day window — enough to demonstrate the ingestion platform can correctly re-aggregate a genuinely different granularity, not a volume-maximizing default.

## Business reality vs. data-system error

| Phase 1 — business reality | Phase 2 — data-system error |
|---|---|
| Product genuinely goes out of stock | POS record missing |
| Demand genuinely increases | Inventory update delayed |
| Promotion causes higher real demand | EAN/identifier mapping broken |
| Store changes its real assortment | Promotion file not received |
| Product is discontinued | Duplicate transaction |
| Store receives a large replenishment order | Feed arrives late / wrong aggregation |

If you're unsure which side something belongs on: *did this actually happen in the store, or did our systems just fail to tell us about it correctly?* The former is Phase 1; the latter is Phase 2. Never describe Phase 1 output as "clean RAW data" — Phase 1 is simulated reality and has no RAW representation at all. RAW is exclusively Phase 2's output.

## The retailer identity split

A store's retailer *ownership* is a Phase 1 business fact (Store 104 belongs to Retailer A). A retailer's *feed characteristics* are Phase 2 configuration (Retailer A's feed profile: POS = daily, schema = legacy, latency = 1 day, quality = medium). These are two facets of the same real-world entity, kept deliberately decoupled so the business-world model never becomes coupled to the implementation details of how data gets delivered. See [DATA_MODEL.md#retailer-configuration](DATA_MODEL.md#retailer-configuration).

## Ground truth must remain hidden

Phase 1 state is a simulation mechanism, not an analytical data source. It exists only to:

1. generate coherent synthetic data (Phase 1 itself);
2. generate realistic imperfect observations (Phase 2, derived from Phase 1);
3. evaluate the platform objectively (the evaluation harness, offline only).

No module outside Phase 2's generation code and the evaluation harness may import, query, or otherwise access Phase 1 internals. This is enforced architecturally, not just by convention, once the relevant code exists — see [ARCHITECTURE.md#system-boundaries](ARCHITECTURE.md#system-boundaries). The production-like analytical platform must behave as though Phase 1 does not exist. Violating this boundary would make every downstream metric meaningless, since the system would effectively be "grading its own homework" with access to the answer key.

```text
Phase 1 (world) — hidden, persisted, versioned
        │
        ├───────────────┐
        ▼                ▼
Phase 2 (feeds)    Evaluation harness
   → RAW              (test-only, offline)
        │
        ▼
[ everything downstream in ARCHITECTURE.md ]
```

Evaluation is a **separate consumer** of Phase 1, not part of Phase 2. Phase 2 answers "what would a retailer's systems report"; evaluation answers "how good was the platform's inference." Don't let evaluation logic leak into the feeds path, and don't let the feeds path stand in for evaluation.

## Controlled experiments require a persisted, versioned world snapshot

Phase 1's output must be a **persisted, versioned snapshot artifact** — not something regenerated in-process every time Phase 2 runs. This is what makes controlled experiments possible: hold business reality fixed and vary only the observation layer.

```text
World Snapshot v001
        │
        ├── Phase 2 profile: clean retailer feed
        ├── Phase 2 profile: low-quality retailer feed
        ├── Phase 2 profile: medium-quality retailer feed
        └── Phase 2 profile: highly degraded retailer feed
```

All four scenarios derive from the *same* underlying world, so any difference in downstream recommendation accuracy is attributable to data quality, not to a different simulated reality. Without this, questions like "how much does weekly vs. daily POS hurt detection accuracy?" would be confounded — you'd never know whether a result difference came from the data-quality change or from an incidentally different world.

## Canonical semantics (resolved)

Because Phase 2 may intentionally introduce semantic distortions — e.g. reporting `units` as individual items for one retailer but as case-packs for another, or `stock` as store-only for one retailer but store+backroom for another — Phase 1 must define its own semantics in one fixed, unambiguous convention. Otherwise Phase 2's distortions aren't well-defined transformations, and the evaluation harness can't reverse them to score against truth.

**Resolved in `docs/world/02-product-universe.md`:** units are consumer-sellable eaches at the SKU level — whatever a consumer picks up as a single retail item counts as one unit, matching how a POS scan actually works, regardless of what's physically packed inside it. A separate `units_per_case` attribute carries the manufacturer-to-retailer shipping multiplier, so "units" and "cases" are never conflated. Stock (`docs/world/08-inventory.md`) follows the same convention and represents store-front-only sellable stock, not combined store+backroom holdings.

## Unresolved design decisions

Deliberately left open, to be decided during the relevant implementation milestone rather than guessed here:

- **World snapshot format and storage location.** A persisted, versioned snapshot is required (see above); the concrete file format, partitioning, and versioning mechanism are not decided here.
- **Versioning strategy.** How snapshot versions are identified, compared, and reproduced (e.g. semantic versioning vs. content hash vs. simple incrementing ID) is not decided here.

**Resolved since this list was first written** — kept noted here for continuity rather than silently removed:

- **Phase 1 temporal resolution** — daily granularity (store × SKU × day), per Documents 6–9's consistent, converged usage throughout the Ground Truth design; consistent with CLAUDE.md's daily-minimum requirement. Ticket-level POS remains a Phase 2 disaggregation concern, not a reason to raise Phase 1's own resolution.
- **Canonical semantic/unit conventions.** See [Canonical semantics](#canonical-semantics-resolved) above.

## What the hidden state is for

1. **Generating coherent RAW data (via Phase 2)** — sales, inventory, and orders that are causally related to each other and to demand, not independently random.
2. **Deriving realistic imperfections (Phase 2)** — RAW feeds are degraded, retailer-shaped observations of Phase 1, not independently fabricated errors.
3. **Evaluation only** — comparing recommendations against ground truth, exclusively in offline test/evaluation code.

## Evolution

Phase 1 and Phase 2 are developed as two milestones (**M2A — Retail World / Ground Truth** and **M2B — Retailer Feed Simulation**) precisely because they have different responsibilities and different completion criteria: M2A is done when the world is coherent and causally realistic; M2B is done when it can plausibly impersonate several differently-imperfect retailers observing that same world. Both are expected to remain among the most actively developed parts of the codebase throughout the project, since better simulation on either side directly enables better evaluation of everything built on top of it.
