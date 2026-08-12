# Retail Decision Platform

A from-scratch, end-to-end **retail decision intelligence platform**: a synthetic retail world, a data platform that ingests heterogeneous and imperfect retailer feeds, an analytical engine that infers what is happening in stores, and a recommendation engine that turns those inferences into prioritized, explainable actions for commercial teams.

This is a long-term portfolio project. It is built incrementally, in public, with production-style engineering practices — not as a single notebook or a one-off demo.

> **All data is synthetic.** All countries, retailers, brands, products, and people in this project are fictional. The project does not use, reproduce, or expose any real company's proprietary data, business logic, thresholds, or architecture. See [Fictional Data & Originality](#fictional-data--originality) below.

---

## Why this project exists

Real retail data is never clean. Different retailers report sales, inventory, and promotions at different frequencies, in different schemas, with different identifiers, different aggregation levels, and different degrees of trustworthiness. A platform that only works on a single, perfectly-shaped dataset does not reflect how retail analytics actually works in practice.

The central question this project explores:

> **Given imperfect and heterogeneous retail data, can we infer what is happening in stores and produce useful, explainable, and prioritized business recommendations?**

To answer that, the project builds its own imperfect world to analyze. A hidden simulation layer generates a coherent, internally-consistent retail universe (demand, sales, inventory, promotions, seasonality, store and product behavior) and then deliberately degrades what is *observable* from it — the same way real retailer feeds are late, partial, duplicated, mis-mapped, or stale. The analytical pipeline only ever sees the degraded, observable data. The hidden ground truth is used exclusively to evaluate how well the platform did, never to help it decide.

## The problem it solves

Retail commercial teams need to know, every day, a small set of things: which stores likely ran out of stock, which products are underperforming versus a reasonable expectation, where inventory data looks inconsistent with sales, whether a product belongs in a store's assortment, and where placing an order would help. Answering these questions well — and only surfacing the ones worth a human's time — is the job of this platform.

Rather than hardcoding business rules ("if stock < X, flag it"), the project investigates how much of this can be **learned** from historical behavior: peer stores, product behavior, seasonality, promotions, geography. Deterministic baselines are kept as a comparison point, not the end state.

## High-level architecture

```text
Synthetic Retail World (hidden ground truth)
        ↓
Retailer-specific source feeds (heterogeneous, imperfect)
        ↓
RAW
        ↓
Ingestion / orchestration
        ↓
Bronze   (landed, as-received)
        ↓
Data quality + normalization
        ↓
Silver   (conformed, canonical entities)
        ↓
Analytical models / feature engineering
        ↓
Gold     (analysis-ready marts)
        ↓
Detection / inference (availability, underperformance, anomalies, assortment)
        ↓
Recommendation Engine (generation + prioritization)
        ↓
Commercial Agent / User
        ↓
Feedback
        ↓
Model evaluation / improvement
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown of layers, boundaries, and the evaluation loop, and [docs/SIMULATION.md](docs/SIMULATION.md) for how the hidden world state relates to observable data.

## Fictional Data & Originality

Every country market, retailer, retailer feed format, brand, product, and named individual in this project is **synthetically generated and fictional**. Retailer characteristics (feed frequency, schema quirks, data-quality issues) are inspired by *patterns that are common knowledge in the retail analytics industry* — they do not describe, copy, or expose the systems, thresholds, business logic, or data of any specific real company. No proprietary code, configuration, or confidential information from any employer or client is used in this project.

## Planned technology stack

Chosen for being modern, largely free/open-source, and representative of production-style data engineering — not maximal. Decisions and rationale live in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

| Concern | Choice | Why (short) |
|---|---|---|
| Language | Python | Ecosystem fit for data + ML + orchestration |
| Local analytical engine | DuckDB | Fast, embedded, zero-infra OLAP for a solo-scale project |
| Storage format | Parquet | Columnar, portable, plays well with DuckDB/dbt |
| Transformations | dbt Core | Testable, documented, version-controlled SQL transforms |
| Orchestration | Apache Airflow | Industry-standard scheduling, retries, observability |
| Experiment tracking | MLflow (from Milestone 8) | Only once model comparison is actually needed |
| Application layer | Streamlit and/or a FastAPI service | Fastest path to a usable recommendation review UI |
| Containerization | Docker / Docker Compose | Reproducible local + CI environments |
| CI/CD | GitHub Actions | Native to the hosting platform, sufficient for this scale |

## Repository structure

```text
retail-decision-platform/
│
├── docs/               conceptual & architectural documentation
├── simulator/          hidden world-state + synthetic data generation
├── ingestion/          retailer feed adapters, Bronze landing
├── data_quality/       validation rules, fault-injection framework
├── transformations/    Bronze → Silver → Gold (dbt project lives here)
├── models/             analytical / statistical / ML models
├── recommendations/    recommendation generation & prioritization
├── feedback/           commercial agent feedback capture & evaluation
├── orchestration/       Airflow DAGs and scheduling
├── app/                Streamlit / API application layer
├── tests/              automated tests
├── infrastructure/     Docker, environment & deployment config
├── config/             retailer & platform configuration (config-driven, not hardcoded)
├── scripts/            one-off developer utilities
└── README.md
```

Each directory currently contains a short `README.md` describing its intended responsibility. Code is added incrementally, milestone by milestone — see [Roadmap](#roadmap).

## Roadmap

Development proceeds in milestones, each a meaningful capability increase rather than a technical checkbox. Full issue backlog lives on the [GitHub Issues](../../issues) board.

1. **Foundation & Architecture** — domain model, repo structure, tech choices, dev environment
2. **Synthetic Retail World** — first coherent simulation of stores, products, demand, sales, inventory, orders
3. **Retailer Data Feeds** — retailer-specific RAW feeds with varying schema, frequency, and data quality
4. **Data Platform** — ingestion, Bronze/Silver/Gold, data quality checks, dbt transformations
5. **Analytical Engine** — first analytical models and deterministic/statistical baselines
6. **Recommendation Engine** — actionable, prioritized recommendations from analytical outputs
7. **Human Feedback Loop** — simulated/real commercial agent feedback and recommendation evaluation
8. **ML & Adaptive Intelligence** — models that learn expected behavior instead of relying on fixed rules
9. **Orchestration & Productionization** — Airflow, Docker, CI/CD, retries, logging, observability
10. **Application & Portfolio Release** — user-facing interface, diagrams, demonstrations, final write-up

The first working target is a small **end-to-end vertical slice**: one retailer, a handful of stores, a small catalogue, POS + inventory + orders, flowing all the way through to a single recommendation — before the system is broadened. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#incremental-delivery-principle).

## How the components interact

- The **simulator** produces a hidden ground truth and, from it, retailer-shaped observable feeds (RAW).
- **Ingestion** lands those feeds as-received into **Bronze**, per retailer, without altering their structure.
- **Data quality + transformations** conform heterogeneous Bronze data into a canonical **Silver** model, applying validation and identifier resolution.
- **Models / feature engineering** build **Gold** analytical marts from Silver.
- **Detection & inference** models read Gold and produce structured findings (e.g. "likely out of stock").
- The **recommendation engine** turns findings into prioritized, explainable recommendations.
- A **commercial agent** reviews recommendations and provides **feedback** (confirmed, rejected, wrong data, etc.).
- Feedback flows back in as a new data source, used for **evaluation** and, later, **active learning** and confidence calibration.
- Throughout, an **evaluation harness** (test-only) compares recommendations against the simulator's hidden ground truth — something the production pipeline never has access to.

## Status

Early stage — foundation and architecture. See [Milestones](../../milestones) and [Issues](../../issues) for current progress.

## License

[MIT](LICENSE)
