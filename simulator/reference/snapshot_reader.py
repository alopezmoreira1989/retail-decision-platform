"""NovaFoods reference-data layer's narrow, read-only interface onto a
persisted Phase 1 snapshot (simulator/world/snapshot.py's Parquet
output).

Mirrors the discipline simulator/feeds/snapshot_reader.py already
established for Phase 2: an explicit column allow-list, never "read
everything, ignore the rest," so the Latent boundary is enforced by
what gets requested from disk. This module's store allow-list
deliberately excludes `store_scale_class` -- Document 4's Latent
variable must never reach the NovaFoods Store Master, exactly as it
must never reach a retailer feed.

No Phase 1 generator code (simulator.world.clock, .entities, ...) is
imported here -- only the persisted Parquet artifact is read, via
pyarrow, read-only. This module never writes to `snapshot_dir`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pyarrow.parquet as pq

# Deliberately excludes store_scale_class -- Document 4, Latent, must
# never be exposed via the Store Master (or anywhere downstream of it).
_STORE_COLUMNS = (
    "store_id",
    "retailer_id",
    "format",
    "region",
    "address",
    "city",
    "state_province",
    "lat",
    "long",
    "open_date",
    "closure_effective_from",
    "closure_effective_to",
    "closed_date",
)

_SKU_COLUMNS = (
    "sku_id",
    "product_id",
    "units_per_case",
    "pack_size",
    "country",
    "discontinued_on",
    "temp_unavailable_effective_from",
    "temp_unavailable_effective_to",
)

_PRODUCT_COLUMNS = ("product_id", "product_name", "category", "subcategory", "brand")


@dataclass(frozen=True)
class StoreReferenceFact:
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
    closure_effective_from: date | None
    closure_effective_to: date | None
    closed_date: date | None


@dataclass(frozen=True)
class SkuReferenceFact:
    sku_id: str
    product_id: str
    units_per_case: int
    pack_size: str
    country: str
    discontinued_on: date | None
    temp_unavailable_effective_from: date | None
    temp_unavailable_effective_to: date | None


@dataclass(frozen=True)
class ProductReferenceFact:
    product_id: str
    product_name: str
    category: str
    subcategory: str
    brand: str


@dataclass(frozen=True)
class Phase1ReferenceSnapshot:
    stores: tuple[StoreReferenceFact, ...]
    skus: tuple[SkuReferenceFact, ...]
    products: tuple[ProductReferenceFact, ...]


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def read_phase1_reference_snapshot(snapshot_dir: Path) -> Phase1ReferenceSnapshot:
    """Reads stores.parquet, skus.parquet, products.parquet, each
    restricted to its allow-listed columns. Opens files read-only;
    never writes to `snapshot_dir`.
    """
    stores_table = pq.read_table(snapshot_dir / "stores.parquet", columns=list(_STORE_COLUMNS))
    stores = tuple(
        StoreReferenceFact(
            store_id=row["store_id"],
            retailer_id=row["retailer_id"],
            format=row["format"],
            region=row["region"],
            address=row["address"],
            city=row["city"],
            state_province=row["state_province"],
            lat=row["lat"],
            long=row["long"],
            open_date=_parse_date(row["open_date"]),
            closure_effective_from=_parse_date(row["closure_effective_from"]),
            closure_effective_to=_parse_date(row["closure_effective_to"]),
            closed_date=_parse_date(row["closed_date"]),
        )
        for row in stores_table.to_pylist()
    )

    skus_table = pq.read_table(snapshot_dir / "skus.parquet", columns=list(_SKU_COLUMNS))
    skus = tuple(
        SkuReferenceFact(
            sku_id=row["sku_id"],
            product_id=row["product_id"],
            units_per_case=row["units_per_case"],
            pack_size=row["pack_size"],
            country=row["country"],
            discontinued_on=_parse_date(row["discontinued_on"]),
            temp_unavailable_effective_from=_parse_date(row["temp_unavailable_effective_from"]),
            temp_unavailable_effective_to=_parse_date(row["temp_unavailable_effective_to"]),
        )
        for row in skus_table.to_pylist()
    )

    products_table = pq.read_table(
        snapshot_dir / "products.parquet", columns=list(_PRODUCT_COLUMNS)
    )
    products = tuple(
        ProductReferenceFact(
            product_id=row["product_id"],
            product_name=row["product_name"],
            category=row["category"],
            subcategory=row["subcategory"],
            brand=row["brand"],
        )
        for row in products_table.to_pylist()
    )

    return Phase1ReferenceSnapshot(stores=stores, skus=skus, products=products)
