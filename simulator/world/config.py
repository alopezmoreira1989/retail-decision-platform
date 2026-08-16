"""Configuration for Vertical Slice #3 (N stores x N SKUs, explicit
Store x SKU physical assortment, Document 10 promotions).

All numeric values here are simulation-run implementation parameters,
not approved NovaFoods business rules. Documents 6 (Demand), 9
(Orders/Replenishment), and 10 (Promotions & Events) explicitly
delegate exact formulas, distributions, and coefficients to
implementation -- see docs/world/06-demand.md,
docs/world/09-orders-replenishment.md, and
docs/world/10-promotions-events.md.

Structure, not a generic configuration framework: run parameters,
entity parameters, and per-(store, SKU) replenishment/assortment/
promotion parameters are kept as separate, explicit pieces rather than
one flat object, so that adding stores/SKUs/promotions never requires
reshaping unrelated config.
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
class StoreClosureWindow:
    """Document 4 -- OPEN -> TEMPORARILY_CLOSED -> OPEN. Non-terminal,
    so (unlike SkuConfig.discontinued_on) this needs a full window, not
    just a cutover date. Store identity, store_scale_class, format, and
    region are unaffected by closure -- the store reverts to OPEN
    automatically once the window ends, with nothing to reset.
    """

    effective_from: date
    effective_to: date

    def __post_init__(self) -> None:
        if self.effective_from > self.effective_to:
            raise ValueError("StoreClosureWindow: effective_from must not be after effective_to.")


@dataclass(frozen=True)
class StoreConfig:
    """Document 4 fields this slice actually exercises. `region` is a
    minimal grouping label only -- Document 4 explicitly leaves the
    concrete meaning of region as an implementation decision; no real
    geography, boundaries, or demographics are modeled. `closure` is
    None for a store that is never temporarily closed in this config.
    """

    store_id: str
    retailer_id: str
    store_scale_class: int
    format: str
    region: str
    closure: StoreClosureWindow | None


@dataclass(frozen=True)
class SkuConfig:
    """`discontinued_on` is None for a SKU that stays ACTIVE for the
    whole run. Document 2: DISCONTINUED is terminal, so a single
    cutover date is enough -- no window, unlike store closure.
    """

    sku_id: str
    units_per_case: int
    discontinued_on: date | None


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
                              + regional_shock + promotional_log_modifier
                              + idiosyncratic_noise

    Their ratio, not either value alone, is what determines how
    correlated same-region stores end up being -- itself a simulation
    parameter, not a business decision. `promotional_log_modifier`
    (Document 10) is a separate, structurally independent term -- see
    PromotionDemandConfig below and promotions.py.
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

    Whether this policy (or a promotion-adjusted variant of it, see
    promotions.py) is ever actually consulted on a given day is
    decided by clock.py (the causal orchestrator), not by this policy,
    orders.py, or promotions.py.
    """

    review_cadence_days: int
    review_anchor_day_index: int
    order_up_to_level: int
    lead_time_days: int


@dataclass(frozen=True)
class Promotion:
    """Document 10's confirmed Promotion structure -- deliberately not
    a full trade-promotion-management system. `scope` is represented
    as this promotion applying to exactly one (store_id, sku_id) pair
    (Option A -- an explicit pair, not a region/retailer-level
    expansion; that broader scope semantics is not defined by Document
    10 and is deferred, not decided, here).

    Promotion existing for a pair says nothing about whether that pair
    is physically assorted (Document 5) -- no validation here enforces
    it, deliberately: a promotion planned against a SKU that isn't (or
    stops being) carried is a valid Phase 1 scenario. The demand and
    order mechanisms independently gate on sell-eligibility (see
    clock.py), so an unassorted pair's promotion simply never has any
    effect -- not because it is forbidden, but because the existing
    sell-eligibility gate already prevents it.
    """

    promotion_id: str
    store_id: str
    sku_id: str
    promotion_type: str  # "PRICE_PROMOTION" | "NON_PRICE_EVENT"
    discount_depth: float | None  # required iff PRICE_PROMOTION
    origin: str  # "NOVAFOODS_NEGOTIATED" | "RETAILER_UNILATERAL"
    planned_start: date
    planned_end: date
    execution_state: str  # "executed" | "partially_executed" | "not_executed"
    actual_start: date | None
    actual_end: date | None
    # Three-phase demand-modifier window widths (Document 10). Slice
    # configuration, not a business rule -- kept per-promotion so a
    # future config could vary them, though this slice's example
    # config uses the same values throughout.
    pre_phase_days: int
    post_phase_days: int

    def __post_init__(self) -> None:
        if self.planned_start > self.planned_end:
            raise ValueError(
                f"Promotion {self.promotion_id!r}: planned_start must not be after planned_end."
            )
        if self.promotion_type == "NON_PRICE_EVENT" and self.discount_depth is not None:
            raise ValueError(
                f"Promotion {self.promotion_id!r}: NON_PRICE_EVENT must not carry a discount_depth."
            )
        if self.promotion_type == "PRICE_PROMOTION" and not (
            self.discount_depth is not None and self.discount_depth > 0
        ):
            raise ValueError(
                f"Promotion {self.promotion_id!r}: PRICE_PROMOTION requires a positive "
                f"discount_depth."
            )
        if self.execution_state == "not_executed":
            if self.actual_start is not None or self.actual_end is not None:
                raise ValueError(
                    f"Promotion {self.promotion_id!r}: not_executed must not carry "
                    f"actual_start/actual_end."
                )
        else:
            if self.actual_start is None or self.actual_end is None:
                raise ValueError(
                    f"Promotion {self.promotion_id!r}: {self.execution_state} requires "
                    f"actual_start and actual_end."
                )
            if self.actual_start > self.actual_end:
                raise ValueError(
                    f"Promotion {self.promotion_id!r}: actual_start must not be after actual_end."
                )
            if self.execution_state == "executed" and (
                self.actual_start != self.planned_start or self.actual_end != self.planned_end
            ):
                raise ValueError(
                    f"Promotion {self.promotion_id!r}: executed must mirror the planned dates "
                    f"exactly (Document 10: actual defaults to the planned range when fully "
                    f"executed)."
                )
        if self.pre_phase_days < 0 or self.post_phase_days < 0:
            raise ValueError(f"Promotion {self.promotion_id!r}: phase-window widths must be >= 0.")


@dataclass(frozen=True)
class PromotionDemandConfig:
    """Document 10, Effect 1 -- "configurable and stochastic, not a
    universal hardcoded curve." Each promotion's lift/pre/post
    magnitudes (log-space) are drawn once, from these ranges, before
    the day loop (see clock.py) -- not redrawn per day, per pair, or
    per lookup, which is what keeps truncation invariance intact.

    `discount_sensitivity` is the only place discount_depth enters the
    model: it adds to the stochastically-drawn base lift for
    PRICE_PROMOTIONs only. NON_PRICE_EVENTs get the stochastic draw
    alone. This is an implementation formula, not a NovaFoods business
    rule -- Document 10 confirms discount_depth feeds the promotional
    modifier without specifying how.
    """

    lift_log_range: tuple[float, float]
    pre_phase_log_range: tuple[float, float]
    post_phase_log_range: tuple[float, float]
    discount_sensitivity: float


@dataclass(frozen=True)
class PreStockingConfig:
    """Document 10, Effect 2 -- pre-stocking responds to the *planned*
    promotion, only for NovaFoods-negotiated origin (see
    promotions.py). `lead_days` and `multiplier` are simulator
    configuration, not a pre-stocking sizing formula approved anywhere
    in Document 10 (which explicitly delegates it to implementation).
    """

    lead_days: int
    multiplier: float


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
    # Document 10. At most one promotion per (store_id, sku_id) in
    # this slice -- overlapping/stacked promotions on the same pair
    # are a genuine unresolved question Document 10 doesn't address;
    # avoided here as a stated slice limitation, not a Ground Truth
    # rule (see __post_init__).
    promotions: list[Promotion]
    promotion_demand: PromotionDemandConfig
    pre_stocking: PreStockingConfig

    def __post_init__(self) -> None:
        """Strong validation of Document 5's structural invariant:
        physical_assortment(store, sku) implies
        distribution_eligibility(store.retailer, sku). A distribution-
        ineligible SKU must never have a physical assortment window at
        any store -- checked at construction time, not left to be
        discovered later from generated data.

        Also enforces this slice's stated limitation (not a Ground
        Truth rule): at most one promotion per (store_id, sku_id).
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

        seen_pairs: set[tuple[str, str]] = set()
        for promotion in self.promotions:
            pair = (promotion.store_id, promotion.sku_id)
            if pair in seen_pairs:
                raise ValueError(
                    f"More than one promotion targets {pair!r}. Overlapping/stacked "
                    f"promotions on the same (store, SKU) pair are a genuine unresolved "
                    f"question (Document 10 doesn't define precedence or stacking) -- "
                    f"avoided in this slice as a stated limitation, not enforced generally."
                )
            seen_pairs.add(pair)


_START_DATE = date(2026, 1, 1)

# 3 regions x 2 stores each -- every region has a real peer pair for
# the regional-shock correlation mechanism, not just North (2/1
# previously). store_scale_class now spans the full 1-4 range; 4 of
# 6 format taxonomy values used, not maximized. STORE-006 carries a
# closure window (Document 4) -- see below.
_STORES = [
    StoreConfig(
        store_id="STORE-001",
        retailer_id="RETAILER-001",
        store_scale_class=3,
        format="Supermarket",
        region="North",
        closure=None,
    ),
    StoreConfig(
        store_id="STORE-002",
        retailer_id="RETAILER-001",
        store_scale_class=2,
        format="Convenience",
        region="North",
        closure=None,
    ),
    StoreConfig(
        store_id="STORE-003",
        retailer_id="RETAILER-001",
        store_scale_class=3,
        format="Supermarket",
        region="South",
        closure=None,
    ),
    StoreConfig(
        store_id="STORE-004",
        retailer_id="RETAILER-001",
        store_scale_class=4,
        format="Hypermarket",
        region="South",
        closure=None,
    ),
    StoreConfig(
        store_id="STORE-005",
        retailer_id="RETAILER-001",
        store_scale_class=2,
        format="Convenience",
        region="Central",
        closure=None,
    ),
    StoreConfig(
        store_id="STORE-006",
        retailer_id="RETAILER-001",
        store_scale_class=1,
        format="Discount",
        region="Central",
        # Document 4: OPEN -> TEMPORARILY_CLOSED -> OPEN, days 15-22.
        # A new store (not one of the original three), so this event
        # has zero interaction with any existing promotion or the
        # STORE-001/SKU-002 assortment gap. Scenario configuration, not
        # a business rule: chosen (not the ordering policy's
        # lead_time_days) to land inside a delivery already scheduled
        # under the pair's normal lead time -- day 13 is a review day
        # (cadence 7, anchor 6, lead_time_days 3, unmodified), so its
        # delivery on day 16 falls inside this window, demonstrating
        # the "in-transit deliveries are not cancelled" decision without
        # changing that pair's replenishment behavior for the rest of
        # the run.
        closure=StoreClosureWindow(
            effective_from=_START_DATE + timedelta(days=15),
            effective_to=_START_DATE + timedelta(days=22),
        ),
    ),
]

# SKU-003's discontinued_on is set below, after promotions are defined,
# so the date can be chosen with PROMO-004's window visibly in mind.
_SKUS = [
    SkuConfig(sku_id="SKU-001", units_per_case=12, discontinued_on=None),
    SkuConfig(sku_id="SKU-002", units_per_case=24, discontinued_on=None),
    SkuConfig(
        sku_id="SKU-003",
        units_per_case=12,
        # Document 2: ACTIVE -> DISCONTINUED, day 54. Scenario
        # configuration, not a business rule: chosen (not
        # STORE-004/SKU-003's lead_time_days) to land inside a delivery
        # already scheduled under that pair's normal lead time -- day
        # 52 is a review day (cadence 14, anchor 10, lead_time_days 5,
        # unmodified), so its delivery on day 57 falls after this date,
        # demonstrating "in-transit deliveries are not cancelled"
        # without changing that pair's replenishment behavior for the
        # rest of the run. Also comfortably clear of PROMO-004's window
        # (days 30-40, plus its post-phase through day 45, on SKU-003 at
        # STORE-003 -- also carrying this SKU): an earlier date (e.g.
        # day 26) would silently block PROMO-004's already-verified
        # demand lift by making that pair non-sell-eligible before the
        # promotion ever runs, which is exactly the kind of accidental
        # interaction this checkpoint should not introduce.
        discontinued_on=_START_DATE + timedelta(days=54),
    ),
    SkuConfig(sku_id="SKU-004", units_per_case=24, discontinued_on=None),
]

_REGIONS = ["North", "South", "Central"]

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
# STORE-004       carried   carried       carried     -
# STORE-005       carried     -           carried     -
# STORE-006       carried     -             -         -
#
# * STORE-001 / SKU-002: carried days 1-30, gap days 31-40 (Document
#   5's "leaving and returning" case -- just a second row, no new
#   state), carried again from day 41 onward. Dates are slice
#   configuration, not a business rule.
#
# SKU-003 is carried by four stores (002, 003, 004, 005) -- its day-54
# discontinuation (see _SKUS) therefore affects all four simultaneously,
# a stronger demonstration of the catalog-wide pattern than a single
# store would give.
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
    ("STORE-004", "SKU-001"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-004", "SKU-002"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-004", "SKU-003"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-004", "SKU-004"): [],
    ("STORE-005", "SKU-001"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-005", "SKU-002"): [],
    ("STORE-005", "SKU-003"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-005", "SKU-004"): [],
    ("STORE-006", "SKU-001"): [AssortmentWindow(effective_from=_START_DATE, effective_to=None)],
    ("STORE-006", "SKU-002"): [],
    ("STORE-006", "SKU-003"): [],
    ("STORE-006", "SKU-004"): [],
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
    ("STORE-004", "SKU-001"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=13, order_up_to_level=200, lead_time_days=5
    ),
    ("STORE-004", "SKU-002"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=6, order_up_to_level=220, lead_time_days=4
    ),
    ("STORE-004", "SKU-003"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=10, order_up_to_level=200, lead_time_days=5
    ),
    ("STORE-004", "SKU-004"): OrderingPolicy(
        review_cadence_days=14, review_anchor_day_index=13, order_up_to_level=150, lead_time_days=5
    ),
    ("STORE-005", "SKU-001"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=9, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-005", "SKU-002"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=2, order_up_to_level=110, lead_time_days=3
    ),
    ("STORE-005", "SKU-003"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=5, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-005", "SKU-004"): OrderingPolicy(
        review_cadence_days=10, review_anchor_day_index=9, order_up_to_level=90, lead_time_days=3
    ),
    ("STORE-006", "SKU-001"): OrderingPolicy(
        review_cadence_days=7, review_anchor_day_index=6, order_up_to_level=60, lead_time_days=3
    ),
    ("STORE-006", "SKU-002"): OrderingPolicy(
        review_cadence_days=7, review_anchor_day_index=6, order_up_to_level=60, lead_time_days=3
    ),
    ("STORE-006", "SKU-003"): OrderingPolicy(
        review_cadence_days=7, review_anchor_day_index=6, order_up_to_level=60, lead_time_days=3
    ),
    ("STORE-006", "SKU-004"): OrderingPolicy(
        review_cadence_days=7, review_anchor_day_index=6, order_up_to_level=60, lead_time_days=3
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
    ("STORE-004", "SKU-001"): 140,
    ("STORE-004", "SKU-002"): 150,
    ("STORE-004", "SKU-003"): 130,
    ("STORE-004", "SKU-004"): 0,  # never assorted, distribution-ineligible
    ("STORE-005", "SKU-001"): 60,
    ("STORE-005", "SKU-002"): 0,  # never assorted
    ("STORE-005", "SKU-003"): 65,
    ("STORE-005", "SKU-004"): 0,  # never assorted, distribution-ineligible
    ("STORE-006", "SKU-001"): 40,
    ("STORE-006", "SKU-002"): 0,  # never assorted
    ("STORE-006", "SKU-003"): 0,  # never assorted
    ("STORE-006", "SKU-004"): 0,  # never assorted, distribution-ineligible
}

# Document 10. Five promotions, each demonstrating a distinct required
# case (see the Vertical Slice #3 design proposal, section 13) -- not
# maximized for count or volume:
#
# PROMO-001 (STORE-001/SKU-001): NovaFoods-negotiated, partially
#   executed (2 days late, mirroring Document 10's own illustrative
#   example) -- pre-stocking fires, but the lift only covers part of
#   the planned window; a small surplus should emerge on its own.
# PROMO-002 (STORE-002/SKU-001): NovaFoods-negotiated, not executed at
#   all -- pre-stocking fires, zero demand lift -- the cleanest surplus
#   case: nothing besides existing mechanics is needed to produce it.
# PROMO-003 (STORE-003/SKU-001): NovaFoods-negotiated, fully executed
#   as planned -- pre-stocking, full lift, real depletion.
# PROMO-004 (STORE-003/SKU-003): retailer-unilateral, NON_PRICE_EVENT,
#   fully executed -- a real demand lift with NO pre-stocking response,
#   since NovaFoods never knew about it in advance.
# PROMO-005 (STORE-001/SKU-003): NovaFoods-negotiated, fully executed,
#   but targets a pair that is NEVER physically assorted -- must
#   produce zero effect throughout, demonstrating promotion != assortment.
_PROMOTIONS: list[Promotion] = [
    Promotion(
        promotion_id="PROMO-001",
        store_id="STORE-001",
        sku_id="SKU-001",
        promotion_type="PRICE_PROMOTION",
        discount_depth=0.20,
        origin="NOVAFOODS_NEGOTIATED",
        planned_start=_START_DATE + timedelta(days=20),
        planned_end=_START_DATE + timedelta(days=33),
        execution_state="partially_executed",
        actual_start=_START_DATE + timedelta(days=22),
        actual_end=_START_DATE + timedelta(days=33),
        pre_phase_days=3,
        post_phase_days=5,
    ),
    Promotion(
        promotion_id="PROMO-002",
        store_id="STORE-002",
        sku_id="SKU-001",
        promotion_type="PRICE_PROMOTION",
        discount_depth=0.25,
        origin="NOVAFOODS_NEGOTIATED",
        planned_start=_START_DATE + timedelta(days=25),
        planned_end=_START_DATE + timedelta(days=38),
        execution_state="not_executed",
        actual_start=None,
        actual_end=None,
        pre_phase_days=3,
        post_phase_days=5,
    ),
    Promotion(
        promotion_id="PROMO-003",
        store_id="STORE-003",
        sku_id="SKU-001",
        promotion_type="PRICE_PROMOTION",
        discount_depth=0.15,
        origin="NOVAFOODS_NEGOTIATED",
        planned_start=_START_DATE + timedelta(days=15),
        planned_end=_START_DATE + timedelta(days=28),
        execution_state="executed",
        actual_start=_START_DATE + timedelta(days=15),
        actual_end=_START_DATE + timedelta(days=28),
        pre_phase_days=3,
        post_phase_days=5,
    ),
    Promotion(
        promotion_id="PROMO-004",
        store_id="STORE-003",
        sku_id="SKU-003",
        promotion_type="NON_PRICE_EVENT",
        discount_depth=None,
        origin="RETAILER_UNILATERAL",
        planned_start=_START_DATE + timedelta(days=30),
        planned_end=_START_DATE + timedelta(days=40),
        execution_state="executed",
        actual_start=_START_DATE + timedelta(days=30),
        actual_end=_START_DATE + timedelta(days=40),
        pre_phase_days=3,
        post_phase_days=5,
    ),
    Promotion(
        promotion_id="PROMO-005",
        store_id="STORE-001",
        sku_id="SKU-003",  # never physically assorted at STORE-001 -- see _ASSORTMENT
        promotion_type="PRICE_PROMOTION",
        discount_depth=0.30,
        origin="NOVAFOODS_NEGOTIATED",
        planned_start=_START_DATE + timedelta(days=10),
        planned_end=_START_DATE + timedelta(days=20),
        execution_state="executed",
        actual_start=_START_DATE + timedelta(days=10),
        actual_end=_START_DATE + timedelta(days=20),
        pre_phase_days=3,
        post_phase_days=5,
    ),
]

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
    promotions=_PROMOTIONS,
    promotion_demand=PromotionDemandConfig(
        lift_log_range=(0.30, 0.60),
        pre_phase_log_range=(-0.15, -0.05),
        post_phase_log_range=(-0.25, -0.10),
        discount_sensitivity=0.5,
    ),
    pre_stocking=PreStockingConfig(lead_days=10, multiplier=1.6),
)
