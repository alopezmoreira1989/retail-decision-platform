"""Vertical Slice #3 driver -- the day-by-day forward generation loop
over multiple (store, SKU) pairs, with explicit, config-driven physical
assortment and Document 10 promotions.

Sequencing per day, matching the approved causal chain exactly, per pair:

    assortment -> sell-eligibility -> actual demand (+ promotional
        modifier, where applicable) -> sales -> order review
        (+ pre-stocking-adjusted policy, where applicable)
        -> inventory state transition

Each (store, SKU) pair is an independent physical replenishment
relationship -- its own assortment, its own inventory, its own
ordering policy -- with two shared inputs across pairs: same-region
stores see the identical regional demand shock on a given day
(Document 6), and a promotion targeting a pair only ever affects that
one pair. There is no cross-store inventory or ordering interaction of
any kind, and promotions never create one either -- see promotions.py.

Determinism / no-lookahead by construction: a single numpy Generator
is advanced in a fixed order that depends only on the number of
regions, (store, SKU) pairs, and configured promotions -- never on the
simulation horizon:

    setup (once, before the day loop):
        for each store, in config order:
            draw store_baseline (1 draw)
        for each SKU, in config order:
            draw sku_popularity (1 draw)
        for each promotion, in config.promotions order:
            draw promotion magnitudes (3 draws: lift, pre, post)

    per day:
        draw regional shocks -- regions in config order (1 draw/region)
        for each (store, SKU) pair, in config order:
            if sell-eligible: draw idiosyncratic demand noise (1 draw)

This is what makes the truncation-invariance test
(tests/simulator/world/test_vertical_slice.py) a structural check of
the acyclicity rule, not just a convention to remember: if any
generator ever depended on the horizon length, on future state, on
another pair's state, or on a promotion's own future dates, a
truncated run would stop matching the prefix of a longer run.

The Cartesian Store x SKU pair set is a simulation tracking universe,
not a business assertion that every store carries every SKU. Physical
assortment is the authoritative Phase 1 representation of whether a
Store x SKU relationship exists. Every pair constructed below is
tracked (it gets a DayRecord every day, which makes it trivial to
later query "why were there no sales here"), but whether it is ever
actually carried -- and when -- is decided entirely by
`config.assortment` (config.py) and read through
`assortment.is_physically_assorted` / `assortment.is_sell_eligible`.
A pair with no configured assortment windows simply stays
not-sell-eligible for its entire tracked history.

Order review is gated on that same sell-eligibility, and the gate
lives here, not in orders.py: orders.py has no awareness of assortment
at all and must not query it -- this module (the causal orchestrator)
decides whether an active replenishment relationship currently exists
for a pair and only calls `orders.place_order_if_due` when it does.
This isn't a new business rule -- Document 9's whole ordering-policy
model presupposes a store-SKU pair that already has a physical shelf
relationship to replenish.

Promotions (Document 10) are wired in the same orchestrator-owns-the-
gate style: demand.py receives a precomputed `promotional_log_modifier`
scalar and has no awareness of Promotion at all; orders.py receives an
already-adjusted `OrderingPolicy` (same policy, `order_up_to_level`
temporarily boosted) and has no awareness of promotions either. Both
promotions.py functions this module calls are pure, single-promotion,
single-day lookups -- never given "the whole promotions table" to scan
for what's coming.

Product/store lifecycle (Documents 2 and 4) needs no separate gate at
all: `assortment.is_sell_eligible` already resolves both day-dependent
states internally and ANDs them into the same sell-eligibility check
that assortment and promotions already flow through. A discontinued
SKU or a temporarily closed store simply becomes not-sell-eligible,
which -- via the gates already described above -- stops demand and new
orders exactly like a non-assorted pair does. `orders.py`, `sales.py`,
`inventory.py`, and `promotions.py` require zero changes for lifecycle
support. Deliveries already scheduled before a lifecycle event are
NOT cancelled (Document 9 has no cancellation concept, and this module
never invents one): `pending_deliveries` / inventory.step_inventory
run unconditionally every day for every pair, so a shipment already in
transit lands on schedule regardless of that pair's sell-eligibility
that day. During exclusion, `Inventory[t+1] = Inventory[t] +
Deliveries[t]` (sales and new orders are both zero, but arriving
deliveries are not suppressed) -- inventory is not "frozen," it is
merely undrawn-down; once any scheduled deliveries are exhausted it
does stay flat, but that is a consequence of no further deliveries
arriving, not a special rule.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

import numpy as np

from simulator.world import assortment as assortment_mod
from simulator.world import demand as demand_mod
from simulator.world import entities as entities_mod
from simulator.world import inventory as inventory_mod
from simulator.world import orders as orders_mod
from simulator.world import promotions as promotions_mod
from simulator.world import sales as sales_mod
from simulator.world.config import AssortmentWindow, SimulationConfig

PairKey = tuple[str, str]  # (store_id, sku_id)


@dataclass(frozen=True)
class DayRecord:
    day_index: int
    date: date
    store_id: str
    sku_id: str
    physical_assortment: bool
    sku_lifecycle_state: str
    store_lifecycle_state: str
    sell_eligible: bool
    available: bool
    potential_demand: float
    promotion_id: str | None
    promotion_phase: str | None
    promotion_log_modifier: float
    actual_demand: int
    opening_inventory: int
    sales: int
    unmet_demand: int
    stockout: bool
    deliveries: int
    closing_inventory: int
    order_placed_quantity: int


@dataclass(frozen=True)
class SliceResult:
    config: SimulationConfig
    stores: list[entities_mod.Store]
    skus: list[entities_mod.Sku]
    products: list[entities_mod.Product]
    days: list[DayRecord]
    orders: list[orders_mod.Order]


def run_slice(config: SimulationConfig, num_days: int | None = None) -> SliceResult:
    """Run the simulation for `num_days` days (defaults to
    config.run.num_days). Passing a smaller `num_days` must reproduce
    the first `num_days` worth of DayRecords of a longer run
    bit-for-bit given the same seed -- the no-lookahead invariant,
    tested explicitly.
    """
    horizon = config.run.num_days if num_days is None else num_days

    stores = [entities_mod.build_store(sc) for sc in config.stores]
    skus = [entities_mod.build_sku(kc) for kc in config.skus]
    # Static reference data -- no RNG involved, built once, before (and
    # entirely independent of) the day loop below. Adding this has zero
    # effect on draw order or truncation invariance.
    products = [entities_mod.build_product(pc) for pc in config.products]

    # Fixed pair order: stores outer, SKUs inner, both in config order.
    # This is the tracking universe (see module docstring) -- every
    # store x every SKU -- not the assortment itself.
    pairs: list[tuple[entities_mod.Store, entities_mod.Sku]] = [
        (store, sku) for store in stores for sku in skus
    ]

    assortment_windows: dict[PairKey, list[AssortmentWindow]] = {
        (store.store_id, sku.sku_id): assortment_mod.build_assortment_windows(store, sku, config)
        for store, sku in pairs
    }

    # At most one promotion per pair (SimulationConfig.__post_init__
    # enforces this as a stated slice limitation, not a Ground Truth
    # rule) -- a plain dict lookup is therefore sufficient.
    promotion_by_pair: dict[PairKey, promotions_mod.Promotion] = {
        (promotion.store_id, promotion.sku_id): promotion for promotion in config.promotions
    }

    rng = np.random.default_rng(config.run.seed)

    store_baseline: dict[str, float] = {}
    for store in stores:  # fixed order -- see module docstring
        store_baseline[store.store_id] = demand_mod.draw_store_baseline(config.demand, store, rng)

    sku_popularity: dict[str, float] = {}
    for sku in skus:  # fixed order -- see module docstring
        sku_popularity[sku.sku_id] = demand_mod.draw_sku_popularity(config.demand, rng)

    potential_demand: dict[PairKey, float] = {
        (store.store_id, sku.sku_id): demand_mod.combine_potential_demand(
            store_baseline[store.store_id], sku_popularity[sku.sku_id]
        )
        for store, sku in pairs
    }

    promotion_magnitudes: dict[str, promotions_mod.PromotionMagnitudes] = {}
    for promotion in config.promotions:  # fixed order -- see module docstring
        promotion_magnitudes[promotion.promotion_id] = promotions_mod.draw_promotion_magnitudes(
            promotion, config.promotion_demand, rng
        )

    opening_inventory: dict[PairKey, int] = {
        (store.store_id, sku.sku_id): config.initial_inventory[(store.store_id, sku.sku_id)]
        for store, sku in pairs
    }
    # Day 1 opening inventory per pair: a fixed slice parameter,
    # independent of any demand, sales, or other downstream output.
    pending_deliveries: dict[PairKey, dict[int, int]] = {key: {} for key in opening_inventory}

    days: list[DayRecord] = []
    orders: list[orders_mod.Order] = []

    for day_index in range(horizon):
        day = config.run.start_date + timedelta(days=day_index)

        regional_shocks = demand_mod.draw_regional_shocks(config.regions, config.demand, rng)

        for store, sku in pairs:  # fixed order -- see module docstring
            key = (store.store_id, sku.sku_id)
            windows = assortment_windows[key]
            policy = config.ordering_policies[key]
            promotion = promotion_by_pair.get(key)

            physically_assorted = assortment_mod.is_physically_assorted(windows, day)
            sku_state = entities_mod.sku_lifecycle_state(sku, day)
            store_state = entities_mod.store_lifecycle_state(store, day)
            sell_eligible = assortment_mod.is_sell_eligible(windows, store, sku, day)
            available = assortment_mod.is_available(sell_eligible, opening_inventory[key])

            if sell_eligible:
                if promotion is not None:
                    phase_effect = promotions_mod.promotion_demand_phase_modifier(
                        promotion, promotion_magnitudes[promotion.promotion_id], day
                    )
                else:
                    phase_effect = promotions_mod.PromotionPhaseEffect(phase=None, log_modifier=0.0)

                actual_demand = demand_mod.draw_actual_demand(
                    potential_demand[key],
                    day,
                    config.demand,
                    regional_shocks[store.region],
                    phase_effect.log_modifier,
                    rng,
                )
            else:
                # Document 6: demand generated only for sell-eligible
                # store-SKU-day triples. A promotion configured on a
                # non-eligible pair (Promotion != Assortment,
                # Document 5) simply never reaches this branch.
                phase_effect = promotions_mod.PromotionPhaseEffect(phase=None, log_modifier=0.0)
                actual_demand = 0

            sales_result = sales_mod.compute_sales(actual_demand, opening_inventory[key])

            # Order gate: an active replenishment relationship exists
            # only while this pair is sell-eligible. orders.py has no
            # awareness of assortment or promotions and is never asked
            # otherwise -- this orchestrator decides, then calls it.
            if sell_eligible:
                effective_policy = policy
                if promotion is not None:
                    boosted_level = promotions_mod.pre_stocking_order_up_to(
                        promotion, day, policy.order_up_to_level, config.pre_stocking
                    )
                    if boosted_level != policy.order_up_to_level:
                        effective_policy = replace(policy, order_up_to_level=boosted_level)
                order = orders_mod.place_order_if_due(
                    store.store_id,
                    sku.sku_id,
                    day_index,
                    day,
                    opening_inventory[key],
                    effective_policy,
                    sku.units_per_case,
                )
            else:
                order = None
            order_quantity = 0
            if order is not None:
                orders.append(order)
                order_quantity = order.quantity
                delivery_day_index = day_index + policy.lead_time_days
                pending_deliveries[key][delivery_day_index] = (
                    pending_deliveries[key].get(delivery_day_index, 0) + order.quantity
                )

            deliveries_today = pending_deliveries[key].pop(day_index, 0)
            closing_inventory = inventory_mod.step_inventory(
                opening_inventory[key], sales_result.sales, deliveries_today
            )

            days.append(
                DayRecord(
                    day_index=day_index,
                    date=day,
                    store_id=store.store_id,
                    sku_id=sku.sku_id,
                    physical_assortment=physically_assorted,
                    sku_lifecycle_state=sku_state,
                    store_lifecycle_state=store_state,
                    sell_eligible=sell_eligible,
                    available=available,
                    potential_demand=potential_demand[key],
                    promotion_id=promotion.promotion_id if promotion is not None else None,
                    promotion_phase=phase_effect.phase,
                    promotion_log_modifier=phase_effect.log_modifier,
                    actual_demand=actual_demand,
                    opening_inventory=opening_inventory[key],
                    sales=sales_result.sales,
                    unmet_demand=sales_result.unmet_demand,
                    stockout=sales_result.stockout,
                    deliveries=deliveries_today,
                    closing_inventory=closing_inventory,
                    order_placed_quantity=order_quantity,
                )
            )

            opening_inventory[key] = closing_inventory

    return SliceResult(
        config=config, stores=stores, skus=skus, products=products, days=days, orders=orders
    )
