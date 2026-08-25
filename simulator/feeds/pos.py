"""POS feed generation (Vertical Slice #1 design brief, Sections 5/7/
8/9; Source & Delivery Model checkpoint, Sections 4/5/8).

POS observes Phase 1 Actual Sales -- never Demand, never Inventory.
Row existence is gated by Phase 1 `sell_eligible`: a store-SKU pair
that was never sell-eligible on a given day never produces a row, in
either profile. A real retailer's POS system has no mechanism to
report zero sales for a product it has never enrolled in its own
product master, so a pair outside `sell_eligible` simply never
appears -- that is a realistic boundary, not a fault.

Within the sell-eligible set, every day's real Phase 1 sales value
(including legitimate zeros) becomes a row's `sales_qty`. A row is
only ever absent, for an otherwise sell-eligible pair, because of a
configured Phase 2 delivery fault (`missing_delivery_periods`) -- that
distinction (missing row != zero sales) is exactly what a future
missing-data detection model needs to be a non-trivial problem, and it
is why this generator never invents a row to "fill in" a missing day.

Row shape, per the approved Source & Delivery Model checkpoint:
`store_code`/`item_code` (retailer-local identifiers, never
NovaFoods-perspective names), `business_date`, `sales_qty` (the
business facts), plus `uom`/`currency_code`/`exported_at` -- realistic
operational baggage a retailer's export would plausibly carry, never
values our analytics needs to interpret them (uom/currency_code are
constant across every row in this slice -- see module-level constants
below -- so there is nothing to actually convert; the columns exist so
a future ETL has to read and validate them, not because this slice
implements a real unit/currency distortion). `exported_at` is the
retailer's own export timestamp (layer A, artifact metadata) and must
never be confused with `delivered_on` (layer B, the simulated delivery
event, carried in the landing manifest -- see landing.py) -- see
identifiers.py and the Source & Delivery Model checkpoint's
distinction between retailer-side and NovaFoods-side metadata.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime, time, timedelta

from simulator.feeds.identifiers import IdentifierScheme, resolve_store_identifier
from simulator.feeds.profiles import PosFaultProfile
from simulator.feeds.snapshot_reader import Phase1PosFact

# Constant operational baggage for this slice. Deliberately the same
# value on every row and identical across Profile A/B (Section 7 of
# the checkpoint: schemas may differ only by casing, never by
# semantic content) -- these fields exist to be read and validated by
# a future ETL, not to encode a real per-retailer distortion yet.
_UOM = "EA"  # consumer sellable eaches -- Document 2's canonical convention
# NovaFoods' initial markets; no per-retailer country attribute exists
# yet (Document 3's Retailer entity is not implemented -- see the
# pre-infrastructure audit, finding H2).
_CURRENCY_CODE = "USD"

# The retailer's own export job is modeled as a fixed overnight batch,
# one day after the business date it reports, at a fixed time -- a
# plausible, simple, fully deterministic rule (no RNG), matching the
# checkpoint's own example timestamp (02:13).
_EXPORT_TIME_OF_DAY = time(2, 13)


def _exported_at(delivery_period: date) -> datetime:
    return datetime.combine(delivery_period + timedelta(days=1), _EXPORT_TIME_OF_DAY)


@dataclass(frozen=True)
class PosRow:
    store_code: str
    item_code: str
    business_date: date
    sales_qty: int
    uom: str
    currency_code: str
    exported_at: datetime


POS_COLUMN_ORDER: tuple[str, ...] = tuple(f.name for f in fields(PosRow))


@dataclass(frozen=True)
class PosArtifact:
    delivery_period: date
    delivered_on: date
    rows: tuple[PosRow, ...]
    is_duplicate: bool = False


def generate_pos_artifacts(
    pos_facts: Sequence[Phase1PosFact],
    all_dates: Sequence[date],
    identifier_scheme: IdentifierScheme,
    baseline_latency_days: int,
    fault_profile: PosFaultProfile | None,
) -> list[PosArtifact]:
    faults = fault_profile or PosFaultProfile()

    facts_by_date: dict[date, list[Phase1PosFact]] = defaultdict(list)
    for fact in pos_facts:
        if fact.sell_eligible:  # Document 5 gate -- see module docstring
            facts_by_date[fact.date].append(fact)

    artifacts: list[PosArtifact] = []
    for day in all_dates:
        if day in faults.missing_delivery_periods:
            continue  # structural Phase 2 fault: no artifact produced at all

        exported_at = _exported_at(day)
        rows: list[PosRow] = []
        for fact in sorted(facts_by_date.get(day, []), key=lambda f: (f.store_id, f.sku_id)):
            store_code = resolve_store_identifier(
                fact.store_id, day, identifier_scheme.store_mapping, faults.store_migration
            )
            if store_code is None:
                continue  # migration gap -- this store has no representation today
            item_code = identifier_scheme.product_mapping[fact.sku_id]
            rows.append(
                PosRow(
                    store_code=store_code,
                    item_code=item_code,
                    business_date=day,
                    sales_qty=fact.sales,
                    uom=_UOM,
                    currency_code=_CURRENCY_CODE,
                    exported_at=exported_at,
                )
            )

        extra_latency = faults.excess_latency_days.get(day, 0)
        delivered_on = day + timedelta(days=baseline_latency_days + extra_latency)
        artifacts.append(
            PosArtifact(delivery_period=day, delivered_on=delivered_on, rows=tuple(rows))
        )

        if day in faults.duplicate_delivery_periods:
            artifacts.append(
                PosArtifact(
                    delivery_period=day,
                    delivered_on=delivered_on,
                    rows=tuple(rows),
                    is_duplicate=True,
                )
            )

    return artifacts
