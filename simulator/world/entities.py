"""Phase 1 entities for Vertical Slice #1.5: N Stores, N SKUs.

Scope note: Documents 2-4 design a full Store/SKU/Product/Retailer
model (Product vs. SKU as separate levels, a full Retailer entity with
its own attributes, distribution eligibility as its own record). This
slice instantiates only the fields its causal chain actually consumes
-- store-SKU pairs fixed ACTIVE/OPEN for the whole window. Retailer is
represented as a bare ID (Document 4 requires a Store to belong to a
Retailer) rather than a full entity, since nothing about this slice
exercises retailer-level attributes.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.world.config import SkuConfig, StoreConfig


@dataclass(frozen=True)
class Store:
    store_id: str
    retailer_id: str
    store_scale_class: int
    format: str
    region: str
    lifecycle_state: str  # "OPEN" | "TEMPORARILY_CLOSED" | "CLOSED"


@dataclass(frozen=True)
class Sku:
    sku_id: str
    units_per_case: int
    lifecycle_state: str  # "ACTIVE" | "TEMPORARILY_UNAVAILABLE" | "DISCONTINUED"


def build_store(store_config: StoreConfig) -> Store:
    return Store(
        store_id=store_config.store_id,
        retailer_id=store_config.retailer_id,
        store_scale_class=store_config.store_scale_class,
        format=store_config.format,
        region=store_config.region,
        lifecycle_state="OPEN",
    )


def build_sku(sku_config: SkuConfig) -> Sku:
    return Sku(
        sku_id=sku_config.sku_id,
        units_per_case=sku_config.units_per_case,
        lifecycle_state="ACTIVE",
    )
