# simulator

Two distinct phases, conceptually (see [../docs/SIMULATION.md](../docs/SIMULATION.md) and [../CLAUDE.md](../CLAUDE.md) for the full reasoning — directories below are planned, not yet created):

- **`world/` — Phase 1.** Generates simulated business reality (demand, sales, inventory, orders, assortment, promotions, events) as a persisted, versioned ground-truth snapshot. No awareness of retailers' data systems.
- **`feeds/` — Phase 2.** Reads a Phase 1 snapshot and produces retailer-specific, imperfect RAW feeds — the only output the rest of the platform may consume.

Phase 1's ground truth is owned by this package and read only by Phase 2 (within `simulator/`) and by the evaluation harness (test-only). It is never imported by ingestion, transformations, models, or recommendations — see [../docs/SIMULATION.md#ground-truth-must-remain-hidden](../docs/SIMULATION.md#ground-truth-must-remain-hidden).
