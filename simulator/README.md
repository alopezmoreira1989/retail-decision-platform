# simulator

Two distinct phases, conceptually (see [../docs/SIMULATION.md](../docs/SIMULATION.md) and [../CLAUDE.md](../CLAUDE.md) for the full reasoning):

- **`world/` — Phase 1.** Generates simulated business reality (demand, sales, inventory, orders, assortment, promotions, events) as a persisted, versioned ground-truth snapshot. No awareness of retailers' data systems.
- **`feeds/` — Phase 2.** Reads a Phase 1 snapshot (read-only, via `snapshot_reader.py`) and produces retailer-specific, imperfect source artifacts under a deterministic `landing/` tree — the only output the rest of the platform may consume once ingestion exists. Vertical Slice #1 (POS + Assortment, one retailer, two feed profiles) is implemented; ingestion/RAW and every later slice are not.

Phase 1's ground truth is owned by this package and read only by Phase 2 (within `simulator/`) and by the evaluation harness (test-only). It is never imported by ingestion, transformations, models, or recommendations — see [../docs/SIMULATION.md#ground-truth-must-remain-hidden](../docs/SIMULATION.md#ground-truth-must-remain-hidden).
