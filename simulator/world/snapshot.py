"""Persists Vertical Slice #1.5 output as Parquet.

PROVISIONAL. This is a placeholder persistence implementation for the
vertical slice only. docs/SIMULATION.md's "World snapshot format and
storage location" and "Versioning strategy" remain open design
decisions and are NOT resolved by this module: output goes to a
clearly non-final location, is not versioned, and should not be taken
as the eventual Ground Truth snapshot architecture.

The fields written here (unmet_demand, stockout) are Phase 1 Ground
Truth facts that must never reach the production platform (Document
8). That boundary is respected structurally, not just by convention:
this module lives entirely inside simulator/world/, which per
simulator/README.md is read only by Phase 2 and by the evaluation
harness -- no ingestion/production code exists yet, and none should
ever import from here.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from simulator.world.clock import SliceResult

PROVISIONAL_OUTPUT_ROOT = Path(__file__).resolve().parent / "output" / "dev_slice"


def write_snapshot(result: SliceResult, output_dir: Path | None = None) -> Path:
    out_dir = output_dir or (PROVISIONAL_OUTPUT_ROOT / f"seed{result.config.run.seed}")
    out_dir.mkdir(parents=True, exist_ok=True)

    daily_table = pa.table(
        {
            "day_index": [d.day_index for d in result.days],
            "date": [d.date.isoformat() for d in result.days],
            "store_id": [d.store_id for d in result.days],
            "sku_id": [d.sku_id for d in result.days],
            "physical_assortment": [d.physical_assortment for d in result.days],
            "sell_eligible": [d.sell_eligible for d in result.days],
            "available": [d.available for d in result.days],
            "potential_demand": [d.potential_demand for d in result.days],
            "actual_demand": [d.actual_demand for d in result.days],
            "opening_inventory": [d.opening_inventory for d in result.days],
            "sales": [d.sales for d in result.days],
            "unmet_demand": [d.unmet_demand for d in result.days],
            "stockout": [d.stockout for d in result.days],
            "deliveries": [d.deliveries for d in result.days],
            "closing_inventory": [d.closing_inventory for d in result.days],
            "order_placed_quantity": [d.order_placed_quantity for d in result.days],
        }
    )
    pq.write_table(daily_table, out_dir / "daily_state.parquet")

    orders_table = pa.table(
        {
            "store_id": [o.store_id for o in result.orders],
            "sku_id": [o.sku_id for o in result.orders],
            "order_date": [o.order_date.isoformat() for o in result.orders],
            "quantity": [o.quantity for o in result.orders],
            "lead_time_days": [o.lead_time_days for o in result.orders],
            "expected_delivery_date": [o.expected_delivery_date.isoformat() for o in result.orders],
        }
    )
    pq.write_table(orders_table, out_dir / "orders.parquet")

    stores_table = pa.table(
        {
            "store_id": [s.store_id for s in result.stores],
            "retailer_id": [s.retailer_id for s in result.stores],
            "store_scale_class": [s.store_scale_class for s in result.stores],
            "format": [s.format for s in result.stores],
            "region": [s.region for s in result.stores],
        }
    )
    pq.write_table(stores_table, out_dir / "stores.parquet")

    skus_table = pa.table(
        {
            "sku_id": [k.sku_id for k in result.skus],
            "units_per_case": [k.units_per_case for k in result.skus],
        }
    )
    pq.write_table(skus_table, out_dir / "skus.parquet")

    return out_dir
