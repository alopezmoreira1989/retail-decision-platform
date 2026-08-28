# CLAUDE.md — Retail Decision Platform

Guidance for any Claude Code session working in this repository. Read this before making architectural decisions, generating data, or scaffolding new modules. When something here conflicts with a file under `docs/`, **this file wins** unless a human explicitly says otherwise — see [Reconciliation history](#reconciliation-history) for background on why that rule exists.

## What this project is

A long-term portfolio project: an end-to-end **retail decision intelligence platform** that ingests heterogeneous, imperfect retailer data, transforms it into analytical datasets, infers what's happening in stores, generates recommendations, prioritizes them, and eventually incorporates commercial-user feedback.

Inspired by patterns common in enterprise retail analytics, but **completely original**. All data, retailers, products, brands, and business entities are synthetic or fictional. Never reproduce proprietary business logic, data, names, thresholds, architecture, or implementation from any real company or project.

The simulator is not the project — it's the controlled laboratory that makes the rest of the system buildable and *evaluable* without real enterprise data. The project's actual subject matter is the decision-intelligence architecture: ingestion → data quality → analytics → inference → recommendations → prioritization → feedback.

**Central question:** given imperfect and heterogeneous observations of a retail environment, can the platform infer what's happening and produce useful, explainable, prioritized recommendations?

## Core architectural philosophy

> The system does not observe reality directly. It observes imperfect representations of reality produced by different retailer systems.

Everything else in this document follows from that sentence. This is the single most important constraint on the project.

## The two-phase simulation model (fundamental constraint)

This is a fixed architectural decision, not a suggestion. Treat it as a constraint on the same level as "don't commit secrets."

### Phase 1 — Retail World / Ground Truth (`simulator/world`, conceptually)

Generates a coherent, internally consistent business reality: stores, products, demand, sales, inventory, orders, assortment, promotions, launches, seasonality, regional effects, commercial activity. Relationships must make causal business sense (demand → sales → inventory depletion → replenishment order → delivery → inventory restored).

Phase 1 **may** contain genuine business phenomena: real stockouts, demand shocks, discontinued products, unusual demand, store-to-store differences.

Phase 1 **must not** contain data-system corruption of any kind: no missing/duplicated rows, no broken identifiers, no delayed feeds, no malformed schemas, no ETL failures, no sync errors. It has no concept of "retailer profile," "feed," "schema," or "fault" — it doesn't know it's being observed.

Phase 1 reports in one fixed, canonical unit convention (e.g., individual units; store-front-only stock) at a time resolution fine enough to support whatever Phase 2 later needs to aggregate or disaggregate (daily minimum). Ticket-level transaction generation is a Phase 2 concern — it's about how a POS system *captures* a day's true sales, not about business reality itself.

Phase 1 output is a **persisted, versioned, seeded artifact**, not something regenerated in-process on every Phase 2 run. This is required for controlled experiments that hold the world fixed while varying retailer/feed configuration (e.g. "does accuracy degrade with weekly vs. daily POS?").

### Phase 2 — Retailer Feed Simulation (`simulator/feeds`, conceptually)

Consumes Phase 1's output through a narrow, read-only interface and simulates what an external retailer's systems would actually transmit: retailer-specific schema, frequency, latency, identifiers, aggregation level, and data-quality/maturity profile. Output is the **RAW data** — the only thing the rest of the platform is allowed to consume.

Retailer variety is **config-driven** (a retailer profile), never hardcoded branches per retailer.

Phase 2 may introduce: missing/duplicate records, delayed feeds, stale inventory, identifier mismatches, schema changes, partial feeds, incorrect mappings, missing promotions, aggregation differences, temporary system failures, historical corrections, and semantic mismatches (e.g. "units" meaning individual items for one retailer and case-packs for another; "stock" meaning store-only vs. store+backroom). Because Phase 1 always reports in one canonical convention, every Phase 2 semantic distortion must be a well-defined, reversible transformation — not an arbitrary relabeling — so evaluation can still score against truth.

Prefer simulated **operational causes** over arbitrary random noise: a POS migration causes a temporary identifier mismatch over a contiguous window; an ETL failure drops a specific day, often clustered (e.g. repeated Sunday failures); a sync delay makes reported stock lag true stock in a specific, explainable direction.

**Scope-bleed rule:** Phase 2 work may only change *how* an existing Phase 1 dynamic is observed or reported. It may never introduce a new business dynamic (e.g. "retailers with worse data also have different real promo lift" belongs in Phase 1, not Phase 2, if it's needed at all).

### The retailer identity split

A store's *ownership* (which retailer chain it belongs to) is a Phase 1 business fact. A retailer's *feed characteristics* (frequency, schema, quality) are Phase 2 configuration. These are two facets of one real-world entity, not a conflict — don't collapse them into a single "retailer" config object.

### The third consumer: evaluation

An evaluation harness also reads Phase 1 directly, but only for **offline scoring**, never for production inference. It is architecturally distinct from Phase 2: Phase 2 answers "what would a retailer's systems report," evaluation answers "how good was the platform's inference." Do not let evaluation logic leak into the feeds path, and do not let the feeds path stand in for evaluation.

```text
                    Phase 1 (world) — hidden, persisted, versioned
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      Phase 2 (feeds) → RAW    Evaluation harness (test-only, offline)
              │
              ▼
      Ingestion → Bronze → Data Quality/Normalization → Silver
              → Analytical Models/Features → Gold
              → Inference → Recommendation Engine → Prioritization
              → Commercial User → Feedback
```

## Business reality vs. data-system error — never confuse these

| Belongs in Phase 1 (reality) | Belongs in Phase 2 (observation error) |
|---|---|
| Product genuinely has no stock | ERP failed to update stock |
| Demand suddenly increases | Sales record went missing |
| Store stops selling a product | Product identifier incorrectly mapped |
| Promotion causes a real demand lift | Promotion not transmitted to us |
| Product is discontinued | Feed arrives late / wrong aggregation |

If you're unsure which side something belongs on, ask: *did this actually happen in the store, or did our systems just fail to tell us about it correctly?* The former is Phase 1; the latter is Phase 2.

## Hidden ground truth — hard boundary

Phase 1 state must never be consumed by the production-like analytical platform, at any layer (ingestion, transformations, models, recommendations, application). It exists only to (1) generate coherent synthetic data, (2) generate imperfect observations via Phase 2, and (3) evaluate the platform objectively, offline. If a change would let any production-path code import or query Phase 1 internals, stop and flag it — this boundary is what makes every downstream metric in the project meaningful.

## Analytical philosophy

Avoid a system built primarily on hardcoded business rules (e.g. "store belongs to cluster X → expected sales = fixed value"). Investigate whether expected behavior can be **learned dynamically** from historical observations: peer stores, product characteristics, seasonality, promotions, geography, regional effects. Candidate approaches — statistical baselines, peer-based models, regression, tree-based ML, anomaly detection, clustering, nearest-neighbors, time-series, probabilistic methods — should be evaluated against each other, not committed to prematurely. Keep a deterministic baseline around specifically so smarter approaches can be objectively compared against it.

## Recommendation philosophy

The analytical layer's job isn't to flag anomalies — it's to produce **actionable recommendations**: availability issues, inventory inconsistencies, underperformance, assortment opportunities, order opportunities, unusual demand, and other commercially relevant situations. Recommendations should eventually carry confidence, expected impact, actionability, priority, and an explanation. Not every anomaly deserves an intervention — prioritization is part of the core design, not an afterthought.

## Human-in-the-loop

Commercial agents review recommendations and respond (confirmed / rejected / already resolved / wrong data / other). Feedback becomes a first-class dataset feeding evaluation and, eventually, precision/false-positive/false-negative tracking, confidence calibration, active learning, and performance breakdowns by retailer and recommendation type.

## Technology direction

Candidate stack, not unconditional requirements — introduce each only when it has a clear architectural purpose, not because it looks good on a CV: Python, SQL, DuckDB, Parquet, dbt Core, Apache Airflow, Docker, MLflow (once experimentation actually needs it), Streamlit and/or an API, GitHub Actions.

## Development principles

1. **Incremental development** — small vertical slices before broadening.
2. **Reproducibility** — synthetic generation, transformations, and experiments should be reproducible (seeded).
3. **Testability** — important business logic is independently testable.
4. **Configuration over hardcoding** — retailer characteristics and simulation parameters are config, not code branches.
5. **Separation of concerns** — keep simulation, feed generation, ingestion, data quality, transformations, analytics, recommendations, feedback, and application as distinct, loosely-coupled layers. No analytical model depends on another model's internals.
6. **Explainability** — recommendations should eventually be understandable to a business user.
7. **Evaluation** — use hidden Phase 1 state only for objective, offline evaluation.
8. **No premature complexity** — don't build distributed infrastructure because it resembles enterprise infrastructure. Start locally; evolve when justified.

## Synthetic data & fictional content — non-negotiable

Initial markets: United States, Canada. Retailers, products, and brands are fictional. Never use real company names, even ones that inspired a pattern. Data should still be realistic enough to support meaningful analytical experiments (correlated, causal, temporally coherent — not independently random).

## Security and confidentiality

Never introduce proprietary information into this repository: no real client names, confidential datasets, copied schemas from proprietary systems, proprietary SQL or business rules, screenshots with confidential content, or internal documentation from any employer or client. The project must stand independently as an original synthetic system.

## Coding standards

Clear, maintainable code over clever code. Type hints where appropriate. Tests for important logic. Focused functions, not giant scripts. Document non-obvious decisions (the *why*, not the *what*). Configuration rather than scattered constants. Avoid unnecessary abstractions. Keep data contracts explicit. Maintain deterministic/reproducible simulation wherever possible.

## Git workflow

- `main` = stable/"prod" branch, protected (PR required, no force-push/deletion).
- `dev` = integration branch for day-to-day work.
- Feature branches off `dev`, merged via PR; `dev` periodically merged into `main`.
- Meaningful commit messages, CI checks and tests passing before merge, issues linked to milestones.
- Full detail: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Decision-making rules for ambiguous situations

1. Preserve the core architecture described in this file.
2. Prefer the simplest design that satisfies the requirement.
3. Do not silently introduce major architectural changes.
4. Explain significant trade-offs rather than picking silently.
5. Avoid implementing speculative functionality not asked for.
6. Ask for clarification when a decision would materially change the architecture.
7. Treat the two-phase simulation model as a fundamental constraint — it is not up for casual revision.

## Where to look for more detail

- [README.md](README.md) — project overview, high-level architecture, roadmap.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system boundaries, RAW/Bronze/Silver/Gold, modularity, evaluation loop.
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) — conceptual entities and relationships.
- [docs/SIMULATION.md](docs/SIMULATION.md) — simulation philosophy, the Phase 1/Phase 2 split, open design decisions.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — branching, local environment, testing, CI.
- [docs/world/](docs/world/) — the incremental, document-by-document design of Phase 1's business model (NovaFoods, products, retailers, stores, demand, ...), reviewed one document at a time before implementation. See [docs/world/README.md](docs/world/README.md) for the process and current status. Do not treat anything in this folder as implemented or final until its status says so.

## Reconciliation history

`docs/SIMULATION.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, the README roadmap, and the GitHub milestones/issues were originally created under an earlier, single-phase framing ("Synthetic Retail World" / "Retailer Data Feeds") before the two-phase model was formalized here. A reconciliation pass has since brought all of them into agreement with this file: GitHub milestones were split (old M2 → **M2A** Retail World/Ground Truth + **M2B** Retailer Feed Simulation; old M4 → **M3** Data Ingestion & Data Quality + **M4** Bronze/Silver/Gold), and the docs above were rewritten accordingly. If a doc or issue ever again describes the old flat M1–M10, single-phase structure, treat that as drift to be fixed, not as current fact — this file remains authoritative.
