"""Assortment feed generation (Vertical Slice #1 design brief,
Sections 6/8/10; Source & Delivery Model checkpoint, Sections 4/6/8).

Represents retailer-reported assortment, read from Phase 1
`physical_assortment` directly -- never from `sell_eligible` and never
from availability/inventory (Document 5's own fundamental invariant:
assortment != sell-eligibility != availability). A weekly snapshot
lists the store-SKU pairs the retailer's own master data currently
believes are carried.

Two independent lag mechanisms, kept deliberately separate:
  - `baseline_latency_days` (structural, both profiles) -- how late the
    snapshot file itself arrives relative to its nominal period. This
    only affects `delivered_on`, never which day's content is reported.
  - `stale_visibility_extra_days` (fault, Profile B only) -- how far
    behind Phase 1 reality the retailer's own system's *belief* about
    assortment lags, independent of transport. This is what produces
    "delayed appearance of a newly carried SKU / delayed removal",
    and it is what shifts `source_as_of_date` earlier than the nominal
    period.
Collapsing these into one number would conflate "the file arrived
late" with "the retailer's own system was already behind reality when
it produced the file" -- two different phenomena with different
downstream evaluation value (freshness detection vs. assortment-state
inference).

Row shape, per the approved Source & Delivery Model checkpoint:
`store_code`/`item_code` (retailer-local identifiers) are the
business facts; `retailer_category_code`, `item_description`,
`record_status_code`, and `exported_at` are realistic operational
baggage a retailer's own product-master export would plausibly carry.
`retailer_category_code` is the retailer's *own* merchandising
taxonomy (Document 2 already anticipated this as a real, out-of-scope
phenomenon) -- deliberately not derived from any NovaFoods category
concept, since none is modeled in this slice either.
`record_status_code` is a constant legacy field (always `"A"`),
included once, never varying -- a plausible enterprise-data artifact
that encodes nothing. None of these fields are derived from, or
capable of revealing, anything beyond what `physical_assortment`
itself already licenses.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime, time, timedelta

from simulator.feeds.identifiers import IdentifierScheme, resolve_store_identifier
from simulator.feeds.profiles import AssortmentFaultProfile
from simulator.feeds.snapshot_reader import Phase1AssortmentFact

# Retailer's own merchandising taxonomy -- deliberately independent of
# any NovaFoods category concept (none is modeled in this slice).
# Deterministic, per-SKU, identical across Profile A/B (Section 7:
# schemas differ only by casing, never by semantic content).
_RETAILER_CATEGORY_CODE_BY_SKU: dict[str, str] = {
    "SKU-001": "DEPT-10",
    "SKU-002": "DEPT-10",
    "SKU-003": "DEPT-20",
    "SKU-004": "DEPT-20",  # never appears in generated output (distribution-ineligible)
}

_RECORD_STATUS_CODE = "A"  # constant legacy field -- see module docstring

_EXPORT_TIME_OF_DAY = time(2, 13)  # matches pos.py's export-batch convention


def _exported_at(delivery_period: date) -> datetime:
    return datetime.combine(delivery_period + timedelta(days=1), _EXPORT_TIME_OF_DAY)


def _item_description(item_code: str) -> str:
    return f"NovaFoods Product {item_code}"


@dataclass(frozen=True)
class AssortmentRow:
    store_code: str
    item_code: str
    retailer_category_code: str
    item_description: str
    record_status_code: str
    exported_at: datetime


ASSORTMENT_COLUMN_ORDER: tuple[str, ...] = tuple(f.name for f in fields(AssortmentRow))


@dataclass(frozen=True)
class AssortmentArtifact:
    delivery_period: date
    delivered_on: date
    source_as_of_date: date
    rows: tuple[AssortmentRow, ...]


def weekly_delivery_periods(
    run_start_date: date, num_days: int, cadence_days: int = 7
) -> list[date]:
    return [run_start_date + timedelta(days=offset) for offset in range(0, num_days, cadence_days)]


def generate_assortment_artifacts(
    assortment_facts: Sequence[Phase1AssortmentFact],
    delivery_periods: Sequence[date],
    run_start_date: date,
    identifier_scheme: IdentifierScheme,
    baseline_latency_days: int,
    fault_profile: AssortmentFaultProfile | None,
) -> list[AssortmentArtifact]:
    faults = fault_profile or AssortmentFaultProfile()

    assorted_by_date: dict[date, set[tuple[str, str]]] = defaultdict(set)
    for fact in assortment_facts:
        if fact.physical_assortment:
            assorted_by_date[fact.date].add((fact.store_id, fact.sku_id))

    artifacts: list[AssortmentArtifact] = []
    for period in delivery_periods:
        if period in faults.missing_delivery_periods:
            continue  # structural Phase 2 fault: no artifact produced at all

        source_as_of_date = max(
            run_start_date, period - timedelta(days=faults.stale_visibility_extra_days)
        )
        pairs_as_of_source_date = assorted_by_date.get(source_as_of_date, set())
        exported_at = _exported_at(period)

        rows: list[AssortmentRow] = []
        for store_id, sku_id in sorted(pairs_as_of_source_date):
            store_code = resolve_store_identifier(
                store_id, period, identifier_scheme.store_mapping, faults.store_migration
            )
            if store_code is None:
                continue  # migration gap -- this store has no representation this period
            item_code = identifier_scheme.product_mapping[sku_id]
            rows.append(
                AssortmentRow(
                    store_code=store_code,
                    item_code=item_code,
                    retailer_category_code=_RETAILER_CATEGORY_CODE_BY_SKU[sku_id],
                    item_description=_item_description(item_code),
                    record_status_code=_RECORD_STATUS_CODE,
                    exported_at=exported_at,
                )
            )

        delivered_on = period + timedelta(days=baseline_latency_days)
        artifacts.append(
            AssortmentArtifact(
                delivery_period=period,
                delivered_on=delivered_on,
                source_as_of_date=source_as_of_date,
                rows=tuple(sorted(rows, key=lambda r: (r.store_code, r.item_code))),
            )
        )

    return artifacts
