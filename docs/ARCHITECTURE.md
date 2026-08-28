# Architecture

This document describes the system boundaries, data flow, and design principles of the Retail Decision Platform. It will evolve as the project moves through its milestones — treat it as the current best understanding, not a final spec.

## System boundaries

There are two systems here — **Simulation** and the **Decision Platform** — and the boundary between them is the most important architectural decision in the project. Simulation itself splits into two phases with a one-way dependency; see [SIMULATION.md](SIMULATION.md) for the full reasoning, and [../CLAUDE.md](../CLAUDE.md) for the binding constraint. In outline:

```text
                       SIMULATION
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
          Phase 1                   Phase 2
       Retail World              Feed Simulation
       Ground Truth             (retailer-specific)
       (persisted, versioned)         │
              │                       │
              └───────────┬───────────┘
                           │  (Phase 2 reads Phase 1; nothing else may)
                     Phase 2 output
                           ▼
                       RAW INPUT
                           ▼
                  DECISION PLATFORM
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  Data Quality /      Analytical         Feature
  Normalization         Models          Engineering
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                    Recommendation
                           ▼
                     Commercial User
                           ▼
                       Feedback
```

1. **Simulation** generates both the hidden ground truth (Phase 1) and, from it, the observable RAW data (Phase 2). Nothing in Simulation is part of the production-like pipeline.
2. **The Decision Platform** is everything from RAW onward: ingestion → Bronze → Silver → Gold → analytics → recommendations → feedback. It consumes Phase 2's output exclusively and behaves as though Phase 1 does not exist.

Phase 1's ground truth is used in exactly one place outside Simulation: an **evaluation harness**, which compares recommendations against ground truth for offline experiments (e.g. "how does accuracy degrade as data quality worsens?"). It is a separate consumer from Phase 2 — Phase 2 answers "what would a retailer report," evaluation answers "how good was the platform's inference." No Decision Platform code (ingestion, transformations, models, recommendations, application) may import or query Phase 1 ground truth. This separation is what makes the project's experiments meaningful.

## Data flow

```text
Phase 1 — Retail World / Ground Truth (hidden, persisted, versioned)
        ↓ observed/degraded by Phase 2, per retailer feed profile
Phase 2 — Retailer Feed Simulation
        ↓ produces
Source artifact   — a CSV, an XLSX, a DB-like read: what the retailer's systems hand over
        ↓ via a delivery mechanism (file drop, API-like, DB-like — retailer-profile-specific)
Landing / exchange — e.g. a file-exchange endpoint for file-based feeds; other endpoints for other mechanisms
        ↓ orchestrated ingestion
RAW (BigQuery)                                              ← Decision Platform starts here
        ↓ data quality checks + identifier resolution + normalization
Silver (BigQuery)  — canonical entities, one schema, retailer origin preserved as lineage
        ↓ feature engineering
Gold (BigQuery)    — analysis-ready marts (store-product-day, inventory position, etc.)
        ↓ inference
Detection / prediction models — availability, underperformance, inventory anomaly, assortment
        ↓ generation + scoring
Recommendation Engine
        ↓ review
Commercial Agent / User
        ↓ response
Feedback
        ↓ closes the loop into
Model evaluation / improvement
```

### Source artifact, delivery mechanism, and landing

Phase 2's output is not RAW by itself — it is a **source artifact** (a CSV, an XLSX, a DB-like read), handed off via a **delivery mechanism** (file drop, API-like, DB-like) to a **landing/exchange** endpoint, which ingestion then reads to produce RAW. These are kept as distinct layers, never collapsed into one "data source" concept. Which mechanism and format a given retailer profile plausibly uses is a Phase 2 characteristic (the same category as schema, frequency, and latency); actually operating that mechanism — writing to an exchange endpoint, serving an API — is ingestion-adjacent tooling, outside both Simulation phases. See [SIMULATION.md#source-artifacts-delivery-mechanism-and-landing](SIMULATION.md#source-artifacts-delivery-mechanism-and-landing) for the full reasoning, including why format is deliberately plural (XLSX for master/small feeds, CSV for large file-based feeds, Parquet as a plausible but non-default option, API-like and DB-like as structured alternatives) and how ticket-level POS fits in as a Phase 2 representation choice, never a Phase 1 resolution.

### RAW

What ingestion produces after reading a retailer's source artifact from its landing/exchange endpoint: retailer-specific, as-received by the (simulated) organization. No two retailers are guaranteed to agree on identifiers, field names, aggregation level, frequency, or completeness. RAW is never mutated after landing. RAW is the first artifact the Decision Platform is allowed to touch — everything upstream of it (Phase 1, Phase 2, the source artifact, and its delivery/landing) is Simulation or Simulation-adjacent tooling, never Decision Platform code.

### Bronze

RAW feeds landed in BigQuery in a consistent *storage* structure, partitioned by retailer/feed/date, without altering their *logical* structure. Bronze is the immutable, replayable record of "what we received and when." Where a retailer profile's aggregation level is ticket-level rather than daily store × SKU, Bronze preserves that ticket-level structure as received — re-aggregation to the canonical daily grain happens in Silver, not here.

### Silver

Bronze conformed into canonical entities (store, product, sale, inventory position, order, promotion, ...) with resolved identifiers and a single schema per entity, regardless of source retailer. This is also where any ticket-level POS gets re-aggregated to the canonical store × SKU × day grain that every other retailer profile already reports at (see [SIMULATION.md](SIMULATION.md) — Phase 1's Sales is always daily store × SKU; ticket-level is only ever a Phase 2 observation choice). Data quality rules are applied and violations are tracked, not silently dropped. Retailer origin and ingestion lineage are preserved as metadata.

### Gold

Silver aggregated and feature-engineered into analysis-ready marts that analytical models consume directly (e.g. `store_product_day`, `inventory_position`, `peer_group_features`). Gold is where "what happened" becomes "what's relevant to decide something."

### Detection / inference

Independent analytical models, each answering one class of question (availability, underperformance, inventory anomaly, assortment fit, demand estimate). Each model is a module with a defined input (Gold tables) and output (structured findings with a confidence). Models do not call each other directly — see [Modularity](#modularity-principle).

### Recommendation engine

Consumes findings from one or more detection models, deduplicates/merges related findings, and produces recommendations with an explanation and a priority score. Prioritization is a function of estimated business impact, model confidence, and actionability — the precise formulation is defined in Milestone 6.

### Feedback

Commercial agent responses to recommendations (confirmed, rejected, already resolved, wrong data, wrong assortment, temporary situation, other) are captured as structured data and become an input to evaluation and, later, model recalibration.

## Warehouse technology and local tooling

**BigQuery is the warehouse** — RAW, Silver, and Gold are BigQuery datasets. It sits after ingestion only; neither Phase 1 nor Phase 2 code ever connects to it directly, and it plays no role in Simulation. The simulator produces source artifacts (see above); the ingestion platform is what loads them into BigQuery.

**DuckDB is local development tooling, not a required hop.** It's useful for local iteration, inspecting generated Parquet output, prototyping transformations, and running tests without cloud dependencies — but `Simulator → DuckDB → BigQuery` is not the architecture. The path is `Simulator → source artifact → ingestion → BigQuery`; DuckDB sits alongside that path for local development, not on it.

## Retention

Configurable, not hardcoded — retention is operational control over data growth, not a claim that older business reality stops existing:

- **RAW and Silver** default to a configurable retention window (initial default: 24 months), implemented via BigQuery table partitioning on business/event date with partition-level expiration — never row-by-row `DELETE`.
- **Gold** has its own, separately configurable retention, typically longer, since Gold marts are small and aggregated and valuable for longitudinal comparison.
- **Source artifacts** (at their landing/exchange endpoint) have an independent retention policy, not tied to warehouse expiration. A source file is never deleted merely because its BigQuery copy aged out.

## Orchestration

Ingestion, transformation (dbt), model scoring, and recommendation generation are pipeline stages with dependencies, not ad hoc scripts. Apache Airflow (Milestone 9) schedules and sequences these stages, handles retries, and provides run-level observability. Before Milestone 9, stages are runnable independently via scripts/CLI for development speed — orchestration is layered on top, not required to get a vertical slice working.

## Modularity principle

No analytical model may depend directly on another analytical model's internals. Models communicate only through Gold tables (inputs) and a shared findings schema (outputs). This keeps the analytical engine extensible: a new detection model is additive, not a change to existing ones. The recommendation engine is the one component allowed to read across multiple models' findings, since combining them is its job.

## Incremental delivery principle

The system is built as a small, complete vertical slice first, then broadened:

```text
1 retailer → few stores → small catalogue → POS + inventory + orders
    → RAW → Silver → one analytical model → one recommendation → simple output
```

Only once this slice works end-to-end does the project add retailers, feeds, data-quality complexity, additional models, and orchestration. This avoids building architecture that has never produced a real recommendation.

## Evaluation loop

```text
Phase 1 — Ground Truth (hidden, persisted, versioned)
        ↓
Phase 2 — Retailer Feed Simulation → RAW
        ↓
Decision Platform (Bronze → Silver → Gold → analytics)
        ↓
Recommendation
        ↓
Compare against Phase 1 ground truth (offline evaluation only)
```

Because Phase 1's output is a persisted, versioned snapshot, the same underlying world can be replayed through Phase 2 with different retailer feed profiles — holding business reality fixed while varying only data quality. This loop is what turns the project from a data-engineering demo into an experimental platform: it enables controlled questions like "does peer-based expected-sales outperform fixed store clusters?" or "how much does daily vs. weekly POS data change detection accuracy?". See [SIMULATION.md](SIMULATION.md) for more on the evaluation philosophy and the open design questions around snapshot versioning.
