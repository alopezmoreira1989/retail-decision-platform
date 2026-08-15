"""Document 5 -- physical assortment and derived sell-eligibility.

Scope note: this slice's single store-SKU pair is assorted for the
entire simulation window -- no assortment-change event is exercised.
Distribution eligibility (Document 5, Layer 2) is not modeled as a
separate record here; it is implicitly true, since a single
retailer/SKU slice has nothing to vary it against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from simulator.world.entities import Sku, Store


@dataclass(frozen=True)
class AssortmentRecord:
    store_id: str
    sku_id: str
    effective_from: date
    effective_to: date | None  # None = open-ended


def build_assortment(store: Store, sku: Sku, start_date: date) -> AssortmentRecord:
    return AssortmentRecord(
        store_id=store.store_id,
        sku_id=sku.sku_id,
        effective_from=start_date,
        effective_to=None,
    )


def is_physically_assorted(assortment: AssortmentRecord, day: date) -> bool:
    if day < assortment.effective_from:
        return False
    if assortment.effective_to is not None and day > assortment.effective_to:
        return False
    return True


def is_sell_eligible(assortment: AssortmentRecord, store: Store, sku: Sku, day: date) -> bool:
    """Document 5, Layer 4 -- derived, never stored."""
    return (
        is_physically_assorted(assortment, day)
        and sku.lifecycle_state == "ACTIVE"
        and store.lifecycle_state == "OPEN"
    )


def is_available(sell_eligible: bool, opening_inventory: int) -> bool:
    """Document 5, Layer 5 -- Availability, a distinct fourth concept,
    never collapsed into sell-eligibility: `available = sell_eligible
    AND physical_inventory > 0`. A sell-eligible SKU with zero stock is
    a stockout, not the same situation as a SKU that was never
    sell-eligible in the first place -- both are "not available," for
    entirely different reasons, and this function is what keeps that
    distinction visible in the generated data rather than only
    reconstructible from other columns.
    """
    return sell_eligible and opening_inventory > 0
