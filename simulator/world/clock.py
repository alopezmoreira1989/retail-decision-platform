"""Vertical Slice #1.5 driver -- the day-by-day forward generation loop
over multiple (store, SKU) pairs.

Sequencing per day, matching the approved causal chain exactly, per pair:

    assortment -> sell-eligibility -> actual demand -> sales
        -> order review -> inventory state transition

Each (store, SKU) pair is an independent physical replenishment
relationship -- its own assortment, its own inventory, its own
ordering policy -- with exactly one shared input across pairs: same-
region stores see the identical regional demand shock on a given day
(Document 6). There is no cross-store inventory or ordering
interaction of any kind.

Determinism / no-lookahead by construction: a single numpy Generator
is advanced in a fixed order that depends only on the number of
regions and (store, SKU) pairs -- never on the simulation horizon:

    setup (once, before the day loop):
        for each (store, SKU) pair, in config order:
            draw potential_demand (2 draws: store baseline, popularity)

    per day:
        draw regional shocks -- regions in config order (1 draw/region)
        for each (store, SKU) pair, in config order:
            draw idiosyncratic demand noise (1 draw)

This is what makes the truncation-invariance test
(tests/simulator/world/test_vertical_slice.py) a structural check of
the acyclicity rule, not just a convention to remember: if any
generator ever depended on the horizon length, on future state, or on
another pair's state, a truncated run would stop matching the prefix
of a longer run.

Slice simplification: the (store, SKU) pair set below is every store
crossed with every SKU. This is a temporary implementation
convenience for exercising N stores x N SKUs, not a claim that every
store carries every SKU as a business fact -- Document 5 makes
physical assortment a Store-SKU relationship that can differ by
store, and `physical_assortment`/`sell_eligible` (assortment.py)
remain the sole authoritative mechanism determining what a store can
actually sell. A future slice that needs partial/varying assortment
across pairs would change which pairs get constructed here, not the
assortment/eligibility logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from simulator.world import assortment as assortment_mod
from simulator.world import demand as demand_mod
from simulator.world import entities as entities_mod
from simulator.world import inventory as inventory_mod
from simulator.world import orders as orders_mod
from simulator.world import sales as sales_mod
from simulator.world.config import SimulationConfig

PairKey = tuple[str, str]  # (store_id, sku_id)


@dataclass(frozen=True)
class DayRecord:
    day_index: int
    date: date
    store_id: str
    sku_id: str
    physical_assortment: bool
    sell_eligible: bool
    available: bool
    potential_demand: float
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

    # Fixed pair order: stores outer, SKUs inner, both in config order.
    # SLICE SIMPLIFICATION, not a business rule: every store x every
    # SKU is evaluated here as a technical convenience. This does not
    # imply every store carries every SKU -- physical_assortment /
    # sell_eligible (assortment.py) remain the authoritative mechanism
    # that actually determines what each store can sell; every pair
    # constructed here still passes through that check independently.
    pairs: list[tuple[entities_mod.Store, entities_mod.Sku]] = [
        (store, sku) for store in stores for sku in skus
    ]

    assortments: dict[PairKey, assortment_mod.AssortmentRecord] = {
        (store.store_id, sku.sku_id): assortment_mod.build_assortment(
            store, sku, config.run.start_date
        )
        for store, sku in pairs
    }

    rng = np.random.default_rng(config.run.seed)

    potential_demand: dict[PairKey, float] = {}
    for store, sku in pairs:  # fixed order -- see module docstring
        potential_demand[(store.store_id, sku.sku_id)] = demand_mod.draw_potential_demand(
            config.demand, store, rng
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
            assortment = assortments[key]
            policy = config.ordering_policies[key]

            physically_assorted = assortment_mod.is_physically_assorted(assortment, day)
            sell_eligible = assortment_mod.is_sell_eligible(assortment, store, sku, day)
            available = assortment_mod.is_available(sell_eligible, opening_inventory[key])

            if sell_eligible:
                actual_demand = demand_mod.draw_actual_demand(
                    potential_demand[key],
                    day,
                    config.demand,
                    regional_shocks[store.region],
                    rng,
                )
            else:
                actual_demand = 0  # Document 6: demand generated only
                # for sell-eligible store-SKU-day triples.

            sales_result = sales_mod.compute_sales(actual_demand, opening_inventory[key])

            order = orders_mod.place_order_if_due(
                store.store_id,
                sku.sku_id,
                day_index,
                day,
                opening_inventory[key],
                policy,
                sku.units_per_case,
            )
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
                    sell_eligible=sell_eligible,
                    available=available,
                    potential_demand=potential_demand[key],
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

    return SliceResult(config=config, stores=stores, skus=skus, days=days, orders=orders)
