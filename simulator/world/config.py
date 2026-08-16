"""Configuration for Vertical Slice #2 (N stores x N SKUs, explicit
Store x SKU physical assortment).

All numeric values here are simulation-run implementation parameters,
not approved NovaFoods business rules. Documents 6 (Demand) and 9
(Orders/Replenishment) explicitly delegate exact formulas,
distributions, and coefficients to implementation -- see
docs/world/06-demand.md and docs/world/09-orders-replenishment.md.

Structure, not a generic configuration framework: run parameters,
entity parameters, and per-(store, SKU) replenishment/assortment
parameters are kept as separate, explicit pieces rather than one flat
object, so that adding stores/SKUs never requires reshaping unrelated
config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class RunConfig:
    seed: int
    start_date: date
    num_days: int


@dataclass(frozen=True)
class StoreConfig:
    """Document 4 fields this slice actually exercises. `region` is a
    minimal grouping label only -- Document 4 explicitly leaves the
    concrete meaning of region as an implementation decision; no real
    geography, boundaries, or demographics are modeled.
    """

    store_id: str
    retailer_id: str
    store_scale_class: int
    format: str
    region: str


@dataclass(frozen=True)
class SkuConfig:
    sku_id: str
    units_per_case: int


@dataclass(frozen=True)
class AssortmentWindow:
    """Document 5 -- one covering period of physical assortment for a
    (store, SKU) pair. A pair with no windows at all was never carried;
    a pair with multiple windows was carried, stopped, and later
    carried again (Document 5: "just a second row," no new state).
    """

    effective_from: date
    effective_to: date | None  # None = open-ended


@dataclass(frozen=True)
class DemandConfig:
    """Document 6 -- illustrative simulation parameters, not business
    rules. `regional_shock_sigma` and `idiosyncratic_noise_sigma` are
    the two components of the log-space demand combination:

        log(actual_demand) = log(potential_demand) + log(seasonal_modifier)
                              + regional_shock + idiosyncratic_noise

    Their ratio, not either value alone, is what determines how
    correlated same-region stores end up being -- itself a simulation
    parameter, not a business decision.
    """

    store_baseline_range_by_tier: dict[int, tuple[float, float]]
    product_popularity_range: tuple[float, float]
    weekday_seasonal_modifiers: dict[int, float]  # 0=Monday ... 6=Sunday
    regional_shock_sigma: float
    idiosyncratic_noise_sigma: float


@dataclass(frozen=True)
class OrderingPolicy:
    """Document 9 -- periodic-review, order-up-to-level policy for one
    (store, SKU) replenishment relationship. `review_anchor_day_index`
    is the day_index of that pair's first review; later reviews occur
    every `review_cadence_days` after that anchor. Kept per-pair
    deliberately -- whether stores sharing a retailer should share a
    review calendar is a business question this slice does not decide;
    an explicit per-pair anchor avoids assuming they do.

    Whether this policy is ever actually consulted on a given day is
    decided by clock.py (the causal orchestrator), not by this policy
    or by orders.py -- see clock.py's order-gating discipline.
    """

    review_cadence_days: int
    review_anchor_day_index: int
    order_up_to_level: int
    lead_time_days: int


@dataclass(frozen=True)
class SimulationConfig:
    run: RunConfig
    stores: list[StoreConfig]
    skus: list[SkuConfig]
    regions: list[str]  # fixed draw order for regional shocks each day
    demand: DemandConfig
    # Retailer-level (Document 5, Layer 2). Single-retailer scope in
    # this slice, so keyed by sku_id alone -- not (retailer_id, sku_id)
    # -- since there is nothing to distinguish it against yet.
    distribution_eligibility: dict[str, bool]
    # Store-level (Document 5, Layer 3), explicit per Option A: no
    # probability model, no store_scale_class -> breadth formula.
    # Keyed by (store_id, sku_id); a missing key or an empty list means
    # that pair was never physically assorted.
    assortment: dict[tuple[str, str], list[AssortmentWindow]]
    # Both keyed by (store_id, sku_id) -- required for every pair in
    # the store x SKU tracking universe (see clock.py), even pairs
    # that are never assorted, where they simply stay inert.
    ordering_policies: dict[tuple[str, str], OrderingPolicy]
    initial_inventory: dict[tuple[str, str], int]

    def __post_init__(self) -> None:
        """Strong validation of Document 5's structural invariant:
        physical_assortment(store, sku) implies
        distribution_eligibility(store.retailer, sku). A distribution-
        ineligible SKU must never have a physical assortment window at
        any store -- checked at construction time, not left to be
        discovered later from generated data.
        """
        for (store_id, sku_id), windows in self.assortment.items():
            if windows and not self.distribution_eligibility.get(sku_id, True):
                raise ValueError(
                    f"SKU {sku_id!r} is distribution-ineligible "
                    f"(distribution_eligibility[{sku_id!r}] = False) but has a "
                    f"physical assortment window at store {store_id!r}. "
                    f"physical_assortment must never exist without "
                    f"distribution_eligibility (Document 5)."
                )


_STORES = [
    StoreConfig(
        store_id="STORE-001",
        retailer_id="RETAILER-001",
        store_scale_class=3,
        format="Supermarket",
        region="North",
    ),
    StoreConfig(
        store_id="STORE-002",
        retailer_id="RETAILER-001",
        store_scale_class=2,
        format="Convenience",
        region="North",
    ),
    StoreConfig(
        store_id="STORE-003",
        retailer_id="RETAILER-001",
        store_scale_class=3,
        format="Supermarket",
        region="South",
    ),
]

_SKUS = [
    SkuConfig(sku_id="SKU-001", units_per_case=12),
    SkuConfig(sku_id="SKU-002", units_per_case=24),
    SkuConfig(sku_id="SKU-003", units_per_case=12),
    SkuConfig(sku_id="SKU-004", units_per_case=24),
]

_REGIONS = ["North", "South"]

_START_DATE = date(2026, 1, 1)

# Document 5, Layer 2. SKU-004 is distribution-ineligible for
# RETAILER-001 -- the sole retailer in this slice -- so no store may
# carry it (enforced by SimulationConfig.__post_init__, not just by
# this table happening to agree with itself).
_DISTRIBUTION_ELIGIBILITY: dict[str, bool] = {
    "SKU-001": True,
    "SKU-002": True,
    "SKU-003": True,
    "SKU-004": False,
}

# Document 5, Layer 3 (Option A -- explicit configuration, no
# probability model, no store_scale_class -> breadth formula; see the
# Vertical Slice #2 design proposal for why that's deferred).
#
#               SKU-001   SKU-002        SKU-003   SKU-004
# STORE-001       carried   carried*        -         -
# STORE-002       carried     -           carried     -
# STORE-003       carried   carried       carried     -
#
# * STORE-001 / SKU-002: carried days 1-30, gap days 31-40 (Document
#   5's "leaving and returning" case -- just a second row, no new
#   state), carried again from day 41 onward. Dates are slice
#   configuration, not a business rule.
_ASSORTMENT: dict[tuple[str, str], list[AssortmentWindow]] = {
    ("STORE-001", "SKU-001"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-001", "SKU-002"): [
        AssortmentWindow(effective_from=_START_DATE, effective_to=_START_DATE + timedelta(days=29)),
        AssortmentWindow(effective_from=_START_DATE + timedelta(days=40), effective_to=None),
    ],
    ("STORE-001", "SKU-003"): [],
    ("STORE-001", "SKU-004"): [],
    ("STORE-002", "SKU-001"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-002", "SKU-002"): [],
    ("STORE-002", "SKU-003"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-002", "SKU-004"): [],
    ("STORE-003", "SKU-001"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-003", "SKU-002"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-003", "SKU-003"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-003", "SKU-004"): [],
}

# Ordering policy and initial inventory are still required for every
# (store, SKU) pair in the tracking universe -- including pairs never
# physically assorted, where they simply stay inert once order review
# is gated by sell-eligibility (see clock.py). Never-assorted pairs
# get initial_inventory = 0: a store has no reason to hold stock of a
# product it doesn't carry.
_ORDERING_POLICIES: dict[tuple[str, str], OrderingPolicy] = {
    ("STORE-001", "SKU-001"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=13, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-001", "SKU-002"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=6, order_up_to_level=180, lead_time_days=4
    ),
    ("STORE-001", "SKU-003"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=13, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-001", "SKU-004"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=13, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-002", "SKU-001"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=9, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-002", "SKU-002"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=2, order_up_to_level=110, lead_time_days=3
    ),
    ("STORE-002", "SKU-003"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=9, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-002", "SKU-004"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=9, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-003", "SKU-001"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=10, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-003", "SKU-002"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=3, order_up_to_level=180, lead_time_days=4
    ),
    ("STORE-003", "SKU-003"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=10, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-003", "SKU-004"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=10, order_up_to_level=150, lead_time_days=5
    ),
}

_INITIAL_INVENTORY: dict[tuple[str, str], int] = {
    ("STORE-001", "SKU-001"): 100,
    ("STORE-001", "SKU-002"): 120,
    ("STORE-001", "SKU-003"): 0,  # never assorted
    ("STORE-001", "SKU-004"): 0,  # never assorted, distribution-ineligible
    ("STORE-002", "SKU-001"): 60,
    ("STORE-002", "SKU-002"): 0,  # never assorted
    ("STORE-002", "SKU-003"): 70,
    ("STORE-002", "SKU-004"): 0,  # never assorted, distribution-ineligible
    ("STORE-003", "SKU-001"): 100,
    ("STORE-003", "SKU-002"): 120,
    ("STORE-003", "SKU-003"): 90,
    ("STORE-003", "SKU-004"): 0,  # never assorted, distribution-ineligible
}

DEFAULT_SIMULATION_CONFIG = SimulationConfig(
    run=RunConfig(seed=42, start_date=_START_DATE, num_days=60),
    stores=_STORES,
    skus=_SKUS,
    regions=_REGIONS,
    demand=DemandConfig(
        store_baseline_range_by_tier={
            1: (20.0, 40.0),
            2: (40.0, 70.0),
            3: (70.0, 110.0),
            4: (110.0, 160.0),
        },
        product_popularity_range=(0.7, 1.3),
        weekday_seasonal_modifiers={
            0: 0.95,  # Monday
            1: 0.95,
            2: 1.0,
            3: 1.0,
            4: 1.05,
            5: 1.2,  # Saturday
            6: 1.1,  # Sunday
        },
        regional_shock_sigma=0.15,
        idiosyncratic_noise_sigma=0.20,
    ),
    distribution_eligibility=_DISTRIBUTION_ELIGIBILITY,
    assortment=_ASSORTMENT,
    ordering_policies=_ORDERING_POLICIES,
    initial_inventory=_INITIAL_INVENTORY,
)
