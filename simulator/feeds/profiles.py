"""RetailerFeedProfile / FeedProfile -- the Phase 2 configuration
concept from the approved Vertical Slice #1 design brief (Section 4),
plus the concrete Profile A / Profile B parameters for this slice
specifically (Sections 6-8). Not a generic multi-retailer or
multi-slice framework -- everything below is scoped to RETAILER-001
and to exactly the two feeds and two profiles this slice covers.

Structural feed absence is represented by a FeedType simply not being
a key in `RetailerFeedProfile.feeds` -- no enabled/disabled flag, so a
feed can never be "configured but disabled" in a way that blurs
structural absence with an operational fault.

Source & Delivery Model checkpoint additions: `source_family` and
`delivery_mechanism` are fixed properties of the *feed type* --
POS is always "transactional" / "cloud_object_landing" (stands in for
GCS), Assortment is always "business_document" / "document_repository"
(stands in for Nextcloud) -- looked up from the small dicts below, not
independently configurable per profile. A retailer's POS feed doesn't
get to "choose" to be a business document; letting each profile set
these independently would let Profile A and B silently disagree about
what a feed structurally *is*. `column_casing` is the one and only
approved schema-level difference between Profile A and Profile B
(Section 7): both profiles emit the identical fields, in the identical
order, differing only in naming convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from simulator.feeds.identifiers import (
    IdentifierScheme,
    StoreIdentifierMigrationFault,
    build_barcode_mapping,
    build_product_mapping,
    build_store_mapping,
)

FeedType = str  # "POS" | "ASSORTMENT" for this slice

# Fixed per feed type -- see module docstring. Not user-configurable,
# not a generic framework: two small lookups, nothing more.
FEED_SOURCE_FAMILY: dict[FeedType, str] = {
    "POS": "transactional",
    "ASSORTMENT": "business_document",
}
FEED_DELIVERY_MECHANISM: dict[FeedType, str] = {
    "POS": "cloud_object_landing",  # stands in for GCS
    "ASSORTMENT": "document_repository",  # stands in for Nextcloud
}

# The one approved schema-level difference between Profile A and
# Profile B (Section 7) -- identical fields/order, casing only.
COLUMN_CASING_LOWER_SNAKE_CASE = "lower_snake_case"
COLUMN_CASING_UPPER_SNAKE_CASE = "upper_snake_case"


@dataclass(frozen=True)
class PosFaultProfile:
    missing_delivery_periods: tuple[date, ...] = ()
    duplicate_delivery_periods: tuple[date, ...] = ()
    excess_latency_days: dict[date, int] = field(default_factory=dict)
    store_migration: StoreIdentifierMigrationFault | None = None


@dataclass(frozen=True)
class AssortmentFaultProfile:
    stale_visibility_extra_days: int = 0
    missing_delivery_periods: tuple[date, ...] = ()
    store_migration: StoreIdentifierMigrationFault | None = None


@dataclass(frozen=True)
class FeedProfile:
    source_family: str
    delivery_mechanism: str
    format: str
    frequency: str
    aggregation_level: str
    baseline_latency_days: int
    column_casing: str
    fault_profile: PosFaultProfile | AssortmentFaultProfile | None = None


@dataclass(frozen=True)
class RetailerFeedProfile:
    retailer_id: str
    identifier_scheme: IdentifierScheme
    feeds: dict[FeedType, FeedProfile]


def build_identifier_scheme(store_ids, sku_ids) -> IdentifierScheme:
    return IdentifierScheme(
        store_mapping=build_store_mapping(store_ids),
        product_mapping=build_product_mapping(sku_ids),
        barcode_mapping=build_barcode_mapping(sku_ids),
    )


# ---------------------------------------------------------------------
# Vertical Slice #1 concrete parameters.
#
# All dates are expressed as day offsets from the Phase 1 snapshot's
# run_start_date, so the profile stays valid regardless of which
# absolute calendar dates a given snapshot run happens to use. These
# are scenario configuration for this slice's illustrative degraded
# profile (per the design brief's own "do not turn illustrative
# numeric parameters into business rules" instruction), not approved
# NovaFoods or retailer business facts.
#
# Every fault below has a distinct, non-overlapping window so each can
# be inspected and tested in isolation:
#   days 10-12   missing POS delivery (simulated ETL failure)
#   day 20       duplicate POS delivery
#   days 33-35   store identifier migration gap (STORE-004)
#   days 48-52   one of these days gets an excess-latency POS event
#                (the exact day is seeded-stochastic; see below)
#   day 21       missing Assortment delivery period
#   (whole run)  Assortment content lags Phase 1 reality by an extra
#                7 days, on top of the 7-day baseline transport
#                latency -- see assortment.py's module docstring for
#                why these two lags are kept separate.
# ---------------------------------------------------------------------

MISSING_POS_DELIVERY_OFFSETS = (10, 11, 12)
DUPLICATE_POS_DELIVERY_OFFSET = 20
EXCESS_LATENCY_ELIGIBLE_OFFSETS = (48, 49, 50, 51, 52)
EXCESS_LATENCY_EXTRA_DAYS = 4
STORE_MIGRATION_STORE_ID = "STORE-004"
STORE_MIGRATION_GAP_START_OFFSET = 33
STORE_MIGRATION_GAP_END_OFFSET = 35
STORE_MIGRATION_NEW_IDENTIFIER = "STORE-B117"
MISSING_ASSORTMENT_DELIVERY_OFFSET = 21
STALE_ASSORTMENT_VISIBILITY_EXTRA_DAYS = 7


def _offset_date(run_start_date: date, offset: int) -> date:
    return run_start_date + timedelta(days=offset)


def build_profile_a(retailer_id: str, store_ids, sku_ids) -> RetailerFeedProfile:
    """Clean/reference profile (Section 6/12): near-ideal timeliness
    and no operational faults, but still retailer-local identifiers --
    "clean" is about data quality, not identifier alignment with
    NovaFoods (Vertical Slice #1 correction).
    """
    scheme = build_identifier_scheme(store_ids, sku_ids)
    return RetailerFeedProfile(
        retailer_id=retailer_id,
        identifier_scheme=scheme,
        feeds={
            "POS": FeedProfile(
                source_family=FEED_SOURCE_FAMILY["POS"],
                delivery_mechanism=FEED_DELIVERY_MECHANISM["POS"],
                format="csv",
                frequency="daily",
                aggregation_level="store_sku_day",
                baseline_latency_days=1,
                column_casing=COLUMN_CASING_LOWER_SNAKE_CASE,
                fault_profile=None,
            ),
            "ASSORTMENT": FeedProfile(
                source_family=FEED_SOURCE_FAMILY["ASSORTMENT"],
                delivery_mechanism=FEED_DELIVERY_MECHANISM["ASSORTMENT"],
                format="csv",
                frequency="weekly",
                aggregation_level="store_sku_snapshot",
                baseline_latency_days=2,
                column_casing=COLUMN_CASING_LOWER_SNAKE_CASE,
                fault_profile=None,
            ),
        },
    )


def build_profile_b(
    retailer_id: str, store_ids, sku_ids, run_start_date: date, seed: int
) -> RetailerFeedProfile:
    """Degraded/legacy profile (Section 7/13): every fault has a
    bounded, explicit, operationally-motivated scope. `seed` governs
    only the one genuinely stochastic element in this slice -- which
    day, within a configured 5-day eligible window, the one-off
    excess-latency event lands on (a one-off transport delay is the
    most plausibly "random" of this slice's faults; the migration and
    the missing-delivery windows are modeled as scheduled/structural
    instead, so they stay fixed per profile regardless of seed).
    """
    scheme = build_identifier_scheme(store_ids, sku_ids)

    migration = StoreIdentifierMigrationFault(
        store_id=STORE_MIGRATION_STORE_ID,
        old_identifier=scheme.store_mapping[STORE_MIGRATION_STORE_ID],
        new_identifier=STORE_MIGRATION_NEW_IDENTIFIER,
        gap_start=_offset_date(run_start_date, STORE_MIGRATION_GAP_START_OFFSET),
        gap_end=_offset_date(run_start_date, STORE_MIGRATION_GAP_END_OFFSET),
    )

    rng = np.random.default_rng(seed)
    excess_latency_offset = int(rng.choice(EXCESS_LATENCY_ELIGIBLE_OFFSETS))

    pos_faults = PosFaultProfile(
        missing_delivery_periods=tuple(
            _offset_date(run_start_date, offset) for offset in MISSING_POS_DELIVERY_OFFSETS
        ),
        duplicate_delivery_periods=(_offset_date(run_start_date, DUPLICATE_POS_DELIVERY_OFFSET),),
        excess_latency_days={
            _offset_date(run_start_date, excess_latency_offset): EXCESS_LATENCY_EXTRA_DAYS
        },
        store_migration=migration,
    )

    assortment_faults = AssortmentFaultProfile(
        stale_visibility_extra_days=STALE_ASSORTMENT_VISIBILITY_EXTRA_DAYS,
        missing_delivery_periods=(
            _offset_date(run_start_date, MISSING_ASSORTMENT_DELIVERY_OFFSET),
        ),
        store_migration=migration,
    )

    return RetailerFeedProfile(
        retailer_id=retailer_id,
        identifier_scheme=scheme,
        feeds={
            "POS": FeedProfile(
                source_family=FEED_SOURCE_FAMILY["POS"],
                delivery_mechanism=FEED_DELIVERY_MECHANISM["POS"],
                format="csv",
                frequency="daily",
                aggregation_level="store_sku_day",
                baseline_latency_days=3,
                column_casing=COLUMN_CASING_UPPER_SNAKE_CASE,
                fault_profile=pos_faults,
            ),
            "ASSORTMENT": FeedProfile(
                source_family=FEED_SOURCE_FAMILY["ASSORTMENT"],
                delivery_mechanism=FEED_DELIVERY_MECHANISM["ASSORTMENT"],
                format="xlsx",
                frequency="weekly",
                aggregation_level="store_sku_snapshot",
                baseline_latency_days=7,
                column_casing=COLUMN_CASING_UPPER_SNAKE_CASE,
                fault_profile=assortment_faults,
            ),
        },
    )
