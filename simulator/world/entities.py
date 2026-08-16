"""Phase 1 entities for N Stores, N SKUs, with day-dependent lifecycle
state (Documents 2 and 4).

Scope note: Documents 2-4 design a full Store/SKU/Product/Retailer
model (Product vs. SKU as separate levels, a full Retailer entity with
its own attributes, distribution eligibility as its own record). This
slice instantiates only the fields its causal chain actually consumes.
Retailer is represented as a bare ID (Document 4 requires a Store to
belong to a Retailer) rather than a full entity, since nothing about
this slice exercises retailer-level attributes.

Lifecycle state is not a static entity attribute -- it varies by day,
the same way physical assortment does. `discontinued_on` (Document 2:
ACTIVE -> DISCONTINUED, terminal, so a single cutover date is enough --
no window needed) and `closure` (Document 4: OPEN -> TEMPORARILY_CLOSED
-> OPEN, non-terminal, so a window is needed) are plain config carried
on the entity; `sku_lifecycle_state`/`store_lifecycle_state` resolve
the state for a given day via pure date comparison -- zero RNG, so
lifecycle configuration has no effect on draw order or truncation
invariance (see clock.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from simulator.world.config import SkuConfig, StoreClosureWindow, StoreConfig


@dataclass(frozen=True)
class Store:
    store_id: str
    retailer_id: str
    store_scale_class: int
    format: str
    region: str
    closure: StoreClosureWindow | None


@dataclass(frozen=True)
class Sku:
    sku_id: str
    units_per_case: int
    discontinued_on: date | None


def build_store(store_config: StoreConfig) -> Store:
    return Store(
        store_id=store_config.store_id,
        retailer_id=store_config.retailer_id,
        store_scale_class=store_config.store_scale_class,
        format=store_config.format,
        region=store_config.region,
        closure=store_config.closure,
    )


def build_sku(sku_config: SkuConfig) -> Sku:
    return Sku(
        sku_id=sku_config.sku_id,
        units_per_case=sku_config.units_per_case,
        discontinued_on=sku_config.discontinued_on,
    )


def sku_lifecycle_state(sku: Sku, day: date) -> str:
    """Document 2: ACTIVE until (and not including) discontinued_on,
    DISCONTINUED from that date onward -- terminal, no return.
    """
    if sku.discontinued_on is not None and day >= sku.discontinued_on:
        return "DISCONTINUED"
    return "ACTIVE"


def store_lifecycle_state(store: Store, day: date) -> str:
    """Document 4: OPEN, except during a configured closure window,
    where it is TEMPORARILY_CLOSED -- non-terminal; the store reverts
    to OPEN automatically once the window ends, with no state to reset
    (same store_id, store_scale_class, format, region throughout).
    """
    if (
        store.closure is not None
        and store.closure.effective_from <= day <= store.closure.effective_to
    ):
        return "TEMPORARILY_CLOSED"
    return "OPEN"
