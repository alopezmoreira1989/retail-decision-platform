"""Configuration for Vertical Slice #1.5 (N stores x N SKUs).

All numeric values here are simulation-run implementation parameters,
not approved NovaFoods business rules. Documents 6 (Demand) and 9
(Orders/Replenishment) explicitly delegate exact formulas,
distributions, and coefficients to implementation -- see
docs/world/06-demand.md and docs/world/09-orders-replenishment.md.

Structure, not a generic configuration framework: run parameters,
entity parameters, and per-(store, SKU) replenishment parameters are
kept as separate, explicit pieces rather than one flat object, so that
adding stores/SKUs never requires reshaping unrelated config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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
    # Both keyed by (store_id, sku_id) -- each (store, SKU) pair is an
    # independent replenishment relationship (Document 9).
    ordering_policies: dict[tuple[str, str], OrderingPolicy]
    initial_inventory: dict[tuple[str, str], int]


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
]

_REGIONS = ["North", "South"]

# Staggered review anchors per pair -- deliberately not all the same,
# to demonstrate that pairs are NOT assumed to share a review
# calendar. Cadence and order-up-to level match Document 9's own
# illustrative example; both remain slice configuration, not business
# rules.
_ORDERING_POLICIES: dict[tuple[str, str], OrderingPolicy] = {
    ("STORE-001", "SKU-001"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=13, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-001", "SKU-002"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=6, order_up_to_level=180, lead_time_days=4
    ),
    ("STORE-002", "SKU-001"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=9, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-002", "SKU-002"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=2, order_up_to_level=110, lead_time_days=3
    ),
    ("STORE-003", "SKU-001"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=10, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-003", "SKU-002"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=3, order_up_to_level=180, lead_time_days=4
    ),
}

_INITIAL_INVENTORY: dict[tuple[str, str], int] = {
    ("STORE-001", "SKU-001"): 100,
    ("STORE-001", "SKU-002"): 120,
    ("STORE-002", "SKU-001"): 60,
    ("STORE-002", "SKU-002"): 70,
    ("STORE-003", "SKU-001"): 100,
    ("STORE-003", "SKU-002"): 120,
}

DEFAULT_SIMULATION_CONFIG = SimulationConfig(
    run=RunConfig(seed=42, start_date=date(2026, 1, 1), num_days=60),
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
    ordering_policies=_ORDERING_POLICIES,
    initial_inventory=_INITIAL_INVENTORY,
)
