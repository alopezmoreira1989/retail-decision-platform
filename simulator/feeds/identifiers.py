"""Deterministic, stable, bijective NovaFoods <-> retailer-local
identifier mapping (Vertical Slice #1 design brief, Sections 4/9).

The mapping is a pure function of the NovaFoods canonical ID -- no
randomness, no seed dependency -- so it is trivially reproducible and
bijective by construction: distinct canonical IDs always produce
distinct retailer-local IDs, since it only ever changes the prefix and
preserves the distinguishing numeric suffix.

Both Profile A and Profile B use this same base mapping scheme.
Profile B's one store-identifier-migration fault (see profiles.py)
overrides it for a single store, for a bounded window, via
`resolve_store_identifier` below -- the base mapping dict itself is
never mutated.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


def _numeric_suffix(entity_id: str) -> str:
    return entity_id.rsplit("-", 1)[-1]


def build_store_mapping(store_ids: Iterable[str]) -> dict[str, str]:
    return {store_id: f"STORE-A{_numeric_suffix(store_id)}" for store_id in store_ids}


def build_product_mapping(sku_ids: Iterable[str]) -> dict[str, str]:
    return {sku_id: f"ITEM-A{_numeric_suffix(sku_id)}" for sku_id in sku_ids}


@dataclass(frozen=True)
class IdentifierScheme:
    store_mapping: dict[str, str]
    product_mapping: dict[str, str]


@dataclass(frozen=True)
class StoreIdentifierMigrationFault:
    """One complete Phase 1 store's retailer-local identifier changes
    exactly once, mid-run -- never store-SKU-level. A store identifier
    can't change for one SKU and stay put for another at the same
    store, since POS and Assortment share one `store_mapping`; both
    feeds must resolve this store's identifier identically for any
    given delivery period, which is exactly what
    `resolve_store_identifier` guarantees by being the single function
    both feed generators call.

    Strictly sequential: `old_identifier` applies before `gap_start`,
    then a gap during which NO artifact (POS or Assortment) represents
    this store under any identifier, then `new_identifier` applies
    from `gap_end` onward -- never an overlap. The underlying Phase 1
    store is unchanged throughout; this is purely an observation
    system migration, never a Phase 1 event.
    """

    store_id: str
    old_identifier: str
    new_identifier: str
    gap_start: date
    gap_end: date

    def __post_init__(self) -> None:
        if self.gap_start > self.gap_end:
            raise ValueError("StoreIdentifierMigrationFault: gap_start must not be after gap_end.")


def resolve_store_identifier(
    store_id: str,
    period: date,
    store_mapping: dict[str, str],
    migration: StoreIdentifierMigrationFault | None,
) -> str | None:
    """The retailer-local identifier a store should be represented
    under for one artifact delivery period -- or None if that store
    has no representation at all for this period (the migration gap).

    `period` is always the delivery period the artifact is about (a
    POS day or an Assortment snapshot's nominal period), never a
    business date unrelated to delivery -- the migration is a property
    of the observation/delivery process, not of Phase 1 reality.
    """
    if migration is not None and store_id == migration.store_id:
        if migration.gap_start <= period <= migration.gap_end:
            return None
        if period < migration.gap_start:
            return migration.old_identifier
        return migration.new_identifier
    return store_mapping[store_id]
