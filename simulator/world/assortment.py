"""Document 5 -- physical assortment (as a set of effective-dated
windows per Store x SKU pair) and derived sell-eligibility/availability.

Assortment membership is explicit configuration (Vertical Slice #2,
Option A) -- no probability model, no store_scale_class -> assortment
breadth formula. That generative-formula question is exactly what
Document 5 leaves as "an implementation decision, not designed here";
this slice defers it rather than inventing one. A pair with no
configured windows was never physically assorted; a pair with more
than one window was carried, stopped, and later carried again
(Document 5: "just a second row," no new lifecycle state).

Distribution eligibility (Document 5, Layer 2) is validated at
SimulationConfig construction time (config.py's __post_init__), not
here -- by the time a window list reaches this module, the invariant
`physical_assortment implies distribution_eligibility` already holds
by construction.
"""

from __future__ import annotations

from datetime import date

from simulator.world.config import AssortmentWindow, SimulationConfig
from simulator.world.entities import Sku, Store, sku_lifecycle_state, store_lifecycle_state


def build_assortment_windows(
    store: Store, sku: Sku, config: SimulationConfig
) -> list[AssortmentWindow]:
    return list(config.assortment.get((store.store_id, sku.sku_id), []))


def is_physically_assorted(windows: list[AssortmentWindow], day: date) -> bool:
    return any(
        day >= window.effective_from and (window.effective_to is None or day <= window.effective_to)
        for window in windows
    )


def is_sell_eligible(windows: list[AssortmentWindow], store: Store, sku: Sku, day: date) -> bool:
    """Document 5, Layer 4 -- derived, never stored. Product/store
    lifecycle state is day-dependent (Documents 2 and 4), resolved
    fresh here rather than read from a static attribute -- see
    entities.sku_lifecycle_state / store_lifecycle_state. A
    discontinued SKU or a temporarily closed store fails this check
    exactly the same way a non-assorted pair does; physical_assortment
    itself is never touched by either.
    """
    return (
        is_physically_assorted(windows, day)
        and sku_lifecycle_state(sku, day) == "ACTIVE"
        and store_lifecycle_state(store, day) == "OPEN"
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
