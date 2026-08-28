"""Phase 2's narrow, read-only interface onto a persisted Phase 1
snapshot (simulator/world/snapshot.py's Parquet output).

This module is the only place Phase 2 code touches Phase 1 output
directly, and it deliberately reads a fixed, minimal column set --
store_id, sku_id, date, sell_eligible, sales, physical_assortment --
never the Ground-Truth-only fields snapshot.py also persists
(unmet_demand, stockout, potential_demand, promotion_*, inventory
figures, order figures). Those exist for the evaluation harness only
(Document 8) and must never reach a retailer feed generator, so this
module doesn't even parse them into memory: only the columns listed in
_POS_SOURCE_COLUMNS / _ASSORTMENT_SOURCE_COLUMNS are ever requested
from disk.

No Phase 1 generator code (simulator.world.clock, .demand, .sales, ...)
is imported here -- only the persisted Parquet artifact is read, via
pyarrow, in read-only mode. Phase 2 never regenerates or mutates
Phase 1 state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pyarrow.parquet as pq

# The only Phase 1 columns Phase 2 is ever allowed to read, kept as an
# explicit allow-list (never "read everything, ignore the rest") so
# the read boundary is enforced by what gets requested from disk, not
# just by convention.
_POS_SOURCE_COLUMNS = ("store_id", "sku_id", "date", "sell_eligible", "sales")
_ASSORTMENT_SOURCE_COLUMNS = ("store_id", "sku_id", "date", "physical_assortment")
_DAILY_STATE_COLUMNS = tuple(sorted(set(_POS_SOURCE_COLUMNS) | set(_ASSORTMENT_SOURCE_COLUMNS)))


@dataclass(frozen=True)
class Phase1PosFact:
    store_id: str
    sku_id: str
    date: date
    sell_eligible: bool
    sales: int


@dataclass(frozen=True)
class Phase1AssortmentFact:
    store_id: str
    sku_id: str
    date: date
    physical_assortment: bool


@dataclass(frozen=True)
class Phase1Snapshot:
    retailer_id: str
    store_ids: tuple[str, ...]
    sku_ids: tuple[str, ...]
    run_start_date: date
    run_end_date: date
    pos_facts: tuple[Phase1PosFact, ...]
    assortment_facts: tuple[Phase1AssortmentFact, ...]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def read_phase1_snapshot(snapshot_dir: Path) -> Phase1Snapshot:
    """Reads exactly the Parquet artifacts Phase 2 needs
    (stores.parquet, skus.parquet, daily_state.parquet), each
    restricted to its allow-listed columns. Opens files read-only;
    never writes to `snapshot_dir`.
    """
    stores_table = pq.read_table(
        snapshot_dir / "stores.parquet", columns=["store_id", "retailer_id"]
    )
    store_ids = tuple(stores_table.column("store_id").to_pylist())
    retailer_ids = set(stores_table.column("retailer_id").to_pylist())
    if len(retailer_ids) != 1:
        raise ValueError(
            "Vertical Slice #1 assumes exactly one Phase 1 retailer in the snapshot, "
            f"found {sorted(retailer_ids)}."
        )
    retailer_id = next(iter(retailer_ids))

    skus_table = pq.read_table(snapshot_dir / "skus.parquet", columns=["sku_id"])
    sku_ids = tuple(skus_table.column("sku_id").to_pylist())

    daily_table = pq.read_table(
        snapshot_dir / "daily_state.parquet", columns=list(_DAILY_STATE_COLUMNS)
    )
    rows = daily_table.to_pylist()

    pos_facts = tuple(
        Phase1PosFact(
            store_id=row["store_id"],
            sku_id=row["sku_id"],
            date=_parse_date(row["date"]),
            sell_eligible=row["sell_eligible"],
            sales=row["sales"],
        )
        for row in rows
    )
    assortment_facts = tuple(
        Phase1AssortmentFact(
            store_id=row["store_id"],
            sku_id=row["sku_id"],
            date=_parse_date(row["date"]),
            physical_assortment=row["physical_assortment"],
        )
        for row in rows
    )

    dates = [fact.date for fact in pos_facts]
    run_start_date = min(dates)
    run_end_date = max(dates)

    return Phase1Snapshot(
        retailer_id=retailer_id,
        store_ids=store_ids,
        sku_ids=sku_ids,
        run_start_date=run_start_date,
        run_end_date=run_end_date,
        pos_facts=pos_facts,
        assortment_facts=assortment_facts,
    )
