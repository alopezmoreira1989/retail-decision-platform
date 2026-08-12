# Simulation Philosophy

## Why simulate a whole world instead of generating a dataset

A single, static synthetic dataset would let the project *demonstrate* analytics code, but not *evaluate* it. If there is no notion of what actually happened in a store, there is no way to know whether an "out of stock" recommendation was right. The platform instead simulates a small retail economy with an internal, coherent notion of ground truth, and then generates *observations* of that economy the way real retailers would report them — imperfectly.

This split is what allows the project to ask, and actually answer, questions like: *How much does recommendation accuracy degrade when POS data is weekly instead of daily? Does a peer-based expected-sales model outperform a fixed-cluster baseline? How much does human feedback improve precision over time?*

## Two layers: hidden state vs. observable data

**Hidden simulation state (ground truth).** Maintained internally by the simulator only. Includes the "true" demand for each product at each store on each day, the "true" inventory level, whether a stockout is actually occurring, whether a promotion is actually driving lift, and so on. This state is generated with realistic structure — seasonality, regional effects, holiday effects, promotional lift, store-to-store correlation, product substitution effects — rather than independent random draws per row.

**Observable data (RAW feeds).** Derived *from* the hidden state by a deliberate, retailer-specific degradation process: sampling only what that retailer's systems would actually capture, at that retailer's frequency and aggregation level, with that retailer's identifier scheme, and with data-quality faults injected according to that retailer's profile. This is the only data the analytical pipeline is allowed to read.

```text
Hidden world state (demand, true stock, true stockouts, ...)
        │
        │  retailer-specific observation function
        ▼
Observable RAW feed (partial, delayed, mis-mapped, aggregated, ...)
        │
        ▼
  [ everything downstream in ARCHITECTURE.md ]
```

## Data-quality issues have causes, not just probabilities

Rather than flipping independent coins per field ("5% of rows are null"), the simulator models a small set of **operational fault scenarios**, each with realistic knock-on effects across time and entities. Examples the project intends to support:

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

Modeling *causes* rather than raw noise rates makes the resulting data quality issues internally consistent (e.g. a migration affects a contiguous identifier range and a contiguous time window, not random unrelated rows), which is both more realistic and more useful for testing robustness.

## What the hidden state is for

1. **Generating coherent RAW data** — sales, inventory, and orders that are causally related to each other and to demand, not independently random.
2. **Deriving realistic imperfections** — RAW feeds are degraded versions of the hidden state, not independently fabricated errors.
3. **Evaluation only** — comparing recommendations against ground truth, exclusively in offline test/evaluation code. See [ARCHITECTURE.md#evaluation-loop](ARCHITECTURE.md#evaluation-loop).

## Hard boundary

No module outside the simulator's evaluation harness may import, query, or otherwise access hidden ground truth. This is enforced architecturally (evaluation code lives separately from the production-shaped pipeline and only it is allowed to read simulator internals) rather than by convention alone, once the relevant code exists. Violating this boundary would make every downstream metric meaningless, since the system would effectively be "grading its own homework" with access to the answer key.

## Evolution

The simulator starts simple (Milestone 2: one small coherent world) and grows in realism and scope alongside the rest of the platform (Milestone 3 onward: retailer variety, richer fault models, promotional and assortment dynamics). It is expected to remain one of the most actively developed parts of the codebase throughout the project, since better simulation directly enables better evaluation of everything built on top of it.
