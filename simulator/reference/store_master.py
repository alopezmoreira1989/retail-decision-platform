"""NovaFoods Store Master -- authoritative NovaFoods reference data
(the "NovaFoods-owned reference data" architectural amendment). NOT a
retailer feed: no RetailerFeedProfile, no Profile A/B, no faults, no
retailer-local identifiers. NovaFoods knows this data by construction
(Document 4), the same way it knows its own Orders (Document 9) --
there is no external party being observed here.

`store_scale_class` is never read by snapshot_reader.py (see its own
column allow-list) and therefore cannot appear here even by accident --
Document 4's Latent boundary enforced structurally, not by convention.
`format` remains a legitimate, separate field -- Document 4 states it
is "correlated with, but not identical to" store_scale_class, never a
proxy for it.

Lifecycle is represented as CURRENT STATE as of a single reference
date, not an effective-dated history -- matching how Phase 2's own
feeds already snapshot state per delivery period. The underlying Phase
1 data (closure window, closed_date) still supports a history
representation later if that's ever wanted; this module doesn't build
one now.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from simulator.reference.snapshot_reader import StoreReferenceFact


def _store_lifecycle_state(fact: StoreReferenceFact, reference_date: date) -> str:
    """Same semantics and precedence as
    `simulator.world.entities.store_lifecycle_state` -- re-derived
    here, not imported, so this module keeps reading only Phase 1's
    persisted output (see snapshot_reader.py's module docstring),
    never Phase 1 generator code.
    """
    if fact.closed_date is not None and reference_date >= fact.closed_date:
        return "CLOSED"
    if (
        fact.closure_effective_from is not None
        and fact.closure_effective_to is not None
        and fact.closure_effective_from <= reference_date <= fact.closure_effective_to
    ):
        return "TEMPORARILY_CLOSED"
    return "OPEN"


@dataclass(frozen=True)
class StoreMasterRow:
    store_id: str
    retailer_id: str
    format: str
    region: str
    address: str
    city: str
    state_province: str
    lat: float
    long: float
    open_date: date
    lifecycle_state: str


def generate_store_master(
    stores: tuple[StoreReferenceFact, ...], reference_date: date
) -> list[StoreMasterRow]:
    return [
        StoreMasterRow(
            store_id=fact.store_id,
            retailer_id=fact.retailer_id,
            format=fact.format,
            region=fact.region,
            address=fact.address,
            city=fact.city,
            state_province=fact.state_province,
            lat=fact.lat,
            long=fact.long,
            open_date=fact.open_date,
            lifecycle_state=_store_lifecycle_state(fact, reference_date),
        )
        for fact in stores
    ]
