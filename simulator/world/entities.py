"""Phase 1 entities for N Stores, N SKUs, N Products, with day-dependent
lifecycle state (Documents 2 and 4).

Scope note: Documents 2-4 design a full Store/SKU/Product/Retailer
model, including a full Retailer entity with its own attributes and
distribution eligibility as its own record. This slice instantiates
Store, SKU, and (as of the NovaFoods reference-data checkpoint) Product
-- Retailer is still represented as a bare ID (Document 4 requires a
Store to belong to a Retailer) rather than a full entity, since nothing
about this slice exercises retailer-level attributes.

Lifecycle state is not a static entity attribute -- it varies by day,
the same way physical assortment does. `discontinued_on`/
`temporarily_unavailable` (Document 2) and `closure`/`closed_date`
(Document 4) are plain config carried on the entity;
`sku_lifecycle_state`/`store_lifecycle_state` resolve the state for a
given day via pure date comparison -- zero RNG, so lifecycle
configuration has no effect on draw order or truncation invariance
(see clock.py). `Product` carries no lifecycle of its own -- Document 2
places lifecycle on the SKU, not the Product level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from simulator.world.config import (
    ProductConfig,
    SkuConfig,
    SkuUnavailabilityWindow,
    StoreClosureWindow,
    StoreConfig,
)


@dataclass(frozen=True)
class Store:
    store_id: str
    retailer_id: str
    store_scale_class: int
    format: str
    region: str
    address: str
    city: str
    state_province: str
    lat: float
    long: float
    open_date: date
    closure: StoreClosureWindow | None
    closed_date: date | None


@dataclass(frozen=True)
class Sku:
    sku_id: str
    product_id: str
    units_per_case: int
    pack_size: str
    country: str
    discontinued_on: date | None
    temporarily_unavailable: SkuUnavailabilityWindow | None


@dataclass(frozen=True)
class Product:
    product_id: str
    product_name: str
    category: str
    subcategory: str
    brand: str


def build_store(store_config: StoreConfig) -> Store:
    return Store(
        store_id=store_config.store_id,
        retailer_id=store_config.retailer_id,
        store_scale_class=store_config.store_scale_class,
        format=store_config.format,
        region=store_config.region,
        address=store_config.address,
        city=store_config.city,
        state_province=store_config.state_province,
        lat=store_config.lat,
        long=store_config.long,
        open_date=store_config.open_date,
        closure=store_config.closure,
        closed_date=store_config.closed_date,
    )


def build_sku(sku_config: SkuConfig) -> Sku:
    return Sku(
        sku_id=sku_config.sku_id,
        product_id=sku_config.product_id,
        units_per_case=sku_config.units_per_case,
        pack_size=sku_config.pack_size,
        country=sku_config.country,
        discontinued_on=sku_config.discontinued_on,
        temporarily_unavailable=sku_config.temporarily_unavailable,
    )


def build_product(product_config: ProductConfig) -> Product:
    return Product(
        product_id=product_config.product_id,
        product_name=product_config.product_name,
        category=product_config.category,
        subcategory=product_config.subcategory,
        brand=product_config.brand,
    )


def sku_lifecycle_state(sku: Sku, day: date) -> str:
    """Document 2: ACTIVE, except DISCONTINUED from `discontinued_on`
    onward (terminal, no return) or TEMPORARILY_UNAVAILABLE during a
    configured window (non-terminal; resumes ACTIVE automatically once
    the window ends). DISCONTINUED is checked first because it is
    terminal -- if a SKU is both discontinued and (hypothetically)
    still inside an unavailability window, DISCONTINUED wins, matching
    Document 2's own state diagram where DISCONTINUED has no return.
    """
    if sku.discontinued_on is not None and day >= sku.discontinued_on:
        return "DISCONTINUED"
    if (
        sku.temporarily_unavailable is not None
        and sku.temporarily_unavailable.effective_from
        <= day
        <= sku.temporarily_unavailable.effective_to
    ):
        return "TEMPORARILY_UNAVAILABLE"
    return "ACTIVE"


def store_lifecycle_state(store: Store, day: date) -> str:
    """Document 4: OPEN, except CLOSED from `closed_date` onward
    (terminal, no return -- Document 4: "a new store opening later,
    even at the same address, is a new Store identity") or
    TEMPORARILY_CLOSED during a configured closure window (non-terminal;
    reverts to OPEN automatically once the window ends, with no state
    to reset -- same store_id, store_scale_class, format, region
    throughout). CLOSED is checked first because it is terminal, the
    same precedence `sku_lifecycle_state` gives DISCONTINUED.
    """
    if store.closed_date is not None and day >= store.closed_date:
        return "CLOSED"
    if (
        store.closure is not None
        and store.closure.effective_from <= day <= store.closure.effective_to
    ):
        return "TEMPORARILY_CLOSED"
    return "OPEN"
