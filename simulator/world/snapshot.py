"""Persists Vertical Slice #3 output as Parquet.

PROVISIONAL. This is a placeholder persistence implementation for the
vertical slice only. docs/SIMULATION.md's "World snapshot format and
storage location" and "Versioning strategy" remain open design
decisions and are NOT resolved by this module: output goes to a
clearly non-final location, is not versioned, and should not be taken
as the eventual Ground Truth snapshot architecture.

The fields written here (unmet_demand, stockout, and -- as of the
NovaFoods reference-data checkpoint -- store_scale_class) are Phase 1
Ground Truth facts that must never reach the production platform
(Documents 4 and 8). That boundary is respected structurally, not just
by convention: this module lives entirely inside simulator/world/,
which per simulator/README.md is read only by Phase 2, by
simulator/reference/ (the NovaFoods master-data layer), and by the
evaluation harness -- no ingestion/production code exists yet, and none
should ever import from here. Both downstream readers enforce the
Latent boundary the same way Phase 2 already does: an explicit column
allow-list that never requests store_scale_class from this file.
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
            "sku_lifecycle_state": [d.sku_lifecycle_state for d in result.days],
            "store_lifecycle_state": [d.store_lifecycle_state for d in result.days],
            "sell_eligible": [d.sell_eligible for d in result.days],
            "available": [d.available for d in result.days],
            "potential_demand": [d.potential_demand for d in result.days],
            "promotion_id": [d.promotion_id for d in result.days],
            "promotion_phase": [d.promotion_phase for d in result.days],
            "promotion_log_modifier": [d.promotion_log_modifier for d in result.days],
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
            "address": [s.address for s in result.stores],
            "city": [s.city for s in result.stores],
            "state_province": [s.state_province for s in result.stores],
            "lat": [s.lat for s in result.stores],
            "long": [s.long for s in result.stores],
            "open_date": [s.open_date.isoformat() for s in result.stores],
            "closure_effective_from": [
                s.closure.effective_from.isoformat() if s.closure is not None else None
                for s in result.stores
            ],
            "closure_effective_to": [
                s.closure.effective_to.isoformat() if s.closure is not None else None
                for s in result.stores
            ],
            "closed_date": [
                s.closed_date.isoformat() if s.closed_date is not None else None
                for s in result.stores
            ],
        }
    )
    pq.write_table(stores_table, out_dir / "stores.parquet")

    skus_table = pa.table(
        {
            "sku_id": [k.sku_id for k in result.skus],
            "product_id": [k.product_id for k in result.skus],
            "units_per_case": [k.units_per_case for k in result.skus],
            "pack_size": [k.pack_size for k in result.skus],
            "country": [k.country for k in result.skus],
            "distribution_eligible": [
                result.config.distribution_eligibility.get(k.sku_id, True) for k in result.skus
            ],
            "discontinued_on": [
                k.discontinued_on.isoformat() if k.discontinued_on is not None else None
                for k in result.skus
            ],
            "temp_unavailable_effective_from": [
                k.temporarily_unavailable.effective_from.isoformat()
                if k.temporarily_unavailable is not None
                else None
                for k in result.skus
            ],
            "temp_unavailable_effective_to": [
                k.temporarily_unavailable.effective_to.isoformat()
                if k.temporarily_unavailable is not None
                else None
                for k in result.skus
            ],
        }
    )
    pq.write_table(skus_table, out_dir / "skus.parquet")

    products_table = pa.table(
        {
            "product_id": [p.product_id for p in result.products],
            "product_name": [p.product_name for p in result.products],
            "category": [p.category for p in result.products],
            "subcategory": [p.subcategory for p in result.products],
            "brand": [p.brand for p in result.products],
        }
    )
    pq.write_table(products_table, out_dir / "products.parquet")

    assortment_rows = [
        (store_id, sku_id, window.effective_from.isoformat(), window.effective_to)
        for (store_id, sku_id), windows in result.config.assortment.items()
        for window in windows
    ]
    assortment_table = pa.table(
        {
            "store_id": [row[0] for row in assortment_rows],
            "sku_id": [row[1] for row in assortment_rows],
            "effective_from": [row[2] for row in assortment_rows],
            "effective_to": [
                row[3].isoformat() if row[3] is not None else None for row in assortment_rows
            ],
        }
    )
    pq.write_table(assortment_table, out_dir / "assortment.parquet")

    promotions_table = pa.table(
        {
            "promotion_id": [p.promotion_id for p in result.config.promotions],
            "store_id": [p.store_id for p in result.config.promotions],
            "sku_id": [p.sku_id for p in result.config.promotions],
            "promotion_type": [p.promotion_type for p in result.config.promotions],
            "discount_depth": [p.discount_depth for p in result.config.promotions],
            "origin": [p.origin for p in result.config.promotions],
            "planned_start": [p.planned_start.isoformat() for p in result.config.promotions],
            "planned_end": [p.planned_end.isoformat() for p in result.config.promotions],
            "execution_state": [p.execution_state for p in result.config.promotions],
            "actual_start": [
                p.actual_start.isoformat() if p.actual_start is not None else None
                for p in result.config.promotions
            ],
            "actual_end": [
                p.actual_end.isoformat() if p.actual_end is not None else None
                for p in result.config.promotions
            ],
        }
    )
    pq.write_table(promotions_table, out_dir / "promotions.parquet")

    return out_dir
