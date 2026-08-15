"""Invariant, determinism, and no-lookahead tests for Vertical Slice #1.5
(N stores x N SKUs, with regional demand correlation).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date

import numpy as np

from simulator.world.assortment import is_available
from simulator.world.clock import run_slice
from simulator.world.config import DEFAULT_SIMULATION_CONFIG
from simulator.world.demand import draw_actual_demand, draw_regional_shocks
from simulator.world.sales import compute_sales


def _by_pair(days):
    """Group DayRecords by (store_id, sku_id), each sorted by day_index."""
    grouped = defaultdict(list)
    for day in days:
        grouped[(day.store_id, day.sku_id)].append(day)
    for rows in grouped.values():
        rows.sort(key=lambda d: d.day_index)
    return grouped


def _num_pairs(config) -> int:
    return len(config.stores) * len(config.skus)


# ---------------------------------------------------------------------
# Stockout / availability definitions (pair-agnostic, unit-level)
# ---------------------------------------------------------------------


def test_stockout_definition_does_not_require_zero_opening_inventory():
    """Document 8 (corrected): stockout = unmet_demand > 0, regardless of
    whether opening inventory was exactly zero or merely insufficient.
    """
    positive_inventory_shortfall = compute_sales(actual_demand=100, opening_inventory=60)
    assert positive_inventory_shortfall.unmet_demand == 40
    assert positive_inventory_shortfall.stockout is True

    zero_inventory = compute_sales(actual_demand=45, opening_inventory=0)
    assert zero_inventory.unmet_demand == 45
    assert zero_inventory.stockout is True

    fully_covered = compute_sales(actual_demand=45, opening_inventory=80)
    assert fully_covered.unmet_demand == 0
    assert fully_covered.stockout is False


def test_availability_definition_document_5():
    """Document 5: available = sell_eligible AND physical_inventory > 0,
    a distinct fourth concept, never collapsed into sell-eligibility or
    into stockout.
    """
    assert is_available(sell_eligible=True, opening_inventory=50) is True

    zero_demand = compute_sales(actual_demand=0, opening_inventory=0)
    assert is_available(sell_eligible=True, opening_inventory=0) is False
    assert zero_demand.stockout is False

    positive_demand = compute_sales(actual_demand=30, opening_inventory=0)
    assert is_available(sell_eligible=True, opening_inventory=0) is False
    assert positive_demand.stockout is True

    assert is_available(sell_eligible=False, opening_inventory=999) is False


# ---------------------------------------------------------------------
# Entity generalization
# ---------------------------------------------------------------------


def test_multiple_stores_and_skus_constructed_from_config():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    assert len(result.stores) == len(DEFAULT_SIMULATION_CONFIG.stores) > 1
    assert len(result.skus) == len(DEFAULT_SIMULATION_CONFIG.skus) > 1

    configured_store_ids = {sc.store_id for sc in DEFAULT_SIMULATION_CONFIG.stores}
    configured_sku_ids = {kc.sku_id for kc in DEFAULT_SIMULATION_CONFIG.skus}
    assert {s.store_id for s in result.stores} == configured_store_ids
    assert {k.sku_id for k in result.skus} == configured_sku_ids

    # every configured pair is exercised in the output
    observed_pairs = {(d.store_id, d.sku_id) for d in result.days}
    assert observed_pairs == set(DEFAULT_SIMULATION_CONFIG.ordering_policies.keys())


# ---------------------------------------------------------------------
# Regional demand correlation -- mechanism-level, not a statistical
# result demanded from a small sample.
# ---------------------------------------------------------------------


def test_regional_shocks_one_per_region_in_fixed_order():
    rng = np.random.default_rng(123)
    shocks = draw_regional_shocks(["North", "South"], DEFAULT_SIMULATION_CONFIG.demand, rng)
    assert set(shocks.keys()) == {"North", "South"}
    assert shocks["North"] != shocks["South"]


def test_regional_shocks_deterministic_given_same_rng_state():
    shocks_a = draw_regional_shocks(
        DEFAULT_SIMULATION_CONFIG.regions,
        DEFAULT_SIMULATION_CONFIG.demand,
        np.random.default_rng(7),
    )
    shocks_b = draw_regional_shocks(
        DEFAULT_SIMULATION_CONFIG.regions,
        DEFAULT_SIMULATION_CONFIG.demand,
        np.random.default_rng(7),
    )
    assert shocks_a == shocks_b


def test_regional_shocks_not_autocorrelated_across_days():
    """Region does not deterministically determine demand: two
    successive draws from the same stream (i.e. two different days)
    must differ.
    """
    rng = np.random.default_rng(99)
    shocks_day1 = draw_regional_shocks(
        DEFAULT_SIMULATION_CONFIG.regions, DEFAULT_SIMULATION_CONFIG.demand, rng
    )
    shocks_day2 = draw_regional_shocks(
        DEFAULT_SIMULATION_CONFIG.regions, DEFAULT_SIMULATION_CONFIG.demand, rng
    )
    assert shocks_day1 != shocks_day2


def test_actual_demand_applies_shared_regional_shock_identically():
    """Same potential demand + same regional shock + zero idiosyncratic
    variance must produce identical realized demand -- proving the
    regional shock is a genuine shared multiplier, not something that
    silently varies per call.
    """
    zero_idio_demand_config = replace(
        DEFAULT_SIMULATION_CONFIG.demand, idiosyncratic_noise_sigma=0.0
    )
    a_monday = date(2026, 1, 5)

    demand_a = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.3,
        rng=np.random.default_rng(1),
    )
    demand_b = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.3,
        rng=np.random.default_rng(1),
    )
    assert demand_a == demand_b


def test_actual_demand_changes_with_regional_shock():
    zero_idio_demand_config = replace(
        DEFAULT_SIMULATION_CONFIG.demand, idiosyncratic_noise_sigma=0.0
    )
    a_monday = date(2026, 1, 5)

    higher = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.5,
        rng=np.random.default_rng(1),
    )
    lower = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=-0.5,
        rng=np.random.default_rng(1),
    )
    assert higher > lower


def test_idiosyncratic_noise_independent_between_calls():
    """Same pair-level inputs, same regional shock, successive calls
    from the same RNG stream (i.e. different (store, SKU) pairs on the
    same day) must diverge -- idiosyncratic noise is independent per
    pair, not shared like the regional shock is.
    """
    rng = np.random.default_rng(5)
    a_monday = date(2026, 1, 5)
    demand_a = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=DEFAULT_SIMULATION_CONFIG.demand,
        regional_shock=0.0,
        rng=rng,
    )
    demand_b = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=DEFAULT_SIMULATION_CONFIG.demand,
        regional_shock=0.0,
        rng=rng,
    )
    assert demand_a != demand_b


# ---------------------------------------------------------------------
# Per-row invariants across every generated (day, store, SKU) row
# ---------------------------------------------------------------------


def test_no_sales_outside_assortment_or_eligibility():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        if not day.physical_assortment:
            assert day.sales == 0
        if not day.sell_eligible:
            assert day.sales == 0
            assert day.actual_demand == 0


def test_sales_never_exceed_demand():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        assert day.sales <= day.actual_demand


def test_sales_never_exceed_opening_inventory():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        assert day.sales <= day.opening_inventory


def test_inventory_conservation():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        assert day.closing_inventory == day.opening_inventory - day.sales + day.deliveries


def test_inventory_never_negative():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        assert day.opening_inventory >= 0
        assert day.closing_inventory >= 0


def test_slice_stockout_flags_agree_with_unmet_demand():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        assert day.stockout == (day.unmet_demand > 0)
    assert any(
        day.opening_inventory > 0 and day.unmet_demand > 0 and day.stockout for day in result.days
    )


def test_slice_available_flags_agree_with_definition():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        assert day.available == (day.sell_eligible and day.opening_inventory > 0)
    assert any(not day.available and day.opening_inventory == 0 for day in result.days)


# ---------------------------------------------------------------------
# Pair-aware invariants (per (store, SKU) relationship)
# ---------------------------------------------------------------------


def test_opening_inventory_carries_forward_per_pair():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for rows in _by_pair(result.days).values():
        for prev_day, next_day in zip(rows, rows[1:], strict=False):
            assert next_day.opening_inventory == prev_day.closing_inventory


def test_initial_inventory_is_a_fixed_parameter_not_derived():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    by_pair = _by_pair(result.days)
    for key, expected_initial in DEFAULT_SIMULATION_CONFIG.initial_inventory.items():
        assert by_pair[key][0].opening_inventory == expected_initial

    # changing demand parameters must not change any pair's Day 1
    # opening inventory -- it is a fixed slice parameter, never derived
    # from any demand or sales output.
    altered_demand = replace(DEFAULT_SIMULATION_CONFIG.demand, idiosyncratic_noise_sigma=0.9)
    altered_run = replace(
        DEFAULT_SIMULATION_CONFIG.run, seed=DEFAULT_SIMULATION_CONFIG.run.seed + 1
    )
    altered_config = replace(DEFAULT_SIMULATION_CONFIG, demand=altered_demand, run=altered_run)
    altered_result = run_slice(altered_config)
    altered_by_pair = _by_pair(altered_result.days)
    for key, expected_initial in DEFAULT_SIMULATION_CONFIG.initial_inventory.items():
        assert altered_by_pair[key][0].opening_inventory == expected_initial


def test_orders_placed_only_on_that_pairs_review_days():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for day in result.days:
        if day.order_placed_quantity > 0:
            policy = DEFAULT_SIMULATION_CONFIG.ordering_policies[(day.store_id, day.sku_id)]
            assert day.day_index >= policy.review_anchor_day_index
            assert (
                day.day_index - policy.review_anchor_day_index
            ) % policy.review_cadence_days == 0


def test_orders_do_not_affect_same_day_inventory():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    for order in result.orders:
        assert order.lead_time_days > 0
        order_day_index = (order.order_date - DEFAULT_SIMULATION_CONFIG.run.start_date).days
        delivery_day_index = order_day_index + order.lead_time_days
        assert delivery_day_index != order_day_index


def test_delivery_respects_lead_time_per_pair():
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    rows_by_key = {(d.day_index, d.store_id, d.sku_id): d for d in result.days}
    for order in result.orders:
        order_day_index = (order.order_date - DEFAULT_SIMULATION_CONFIG.run.start_date).days
        delivery_day_index = order_day_index + order.lead_time_days
        lookup_key = (delivery_day_index, order.store_id, order.sku_id)
        if lookup_key in rows_by_key:
            assert rows_by_key[lookup_key].deliveries == order.quantity


# ---------------------------------------------------------------------
# Determinism and no-lookahead
# ---------------------------------------------------------------------


def test_determinism_same_seed_identical_output():
    result_a = run_slice(DEFAULT_SIMULATION_CONFIG)
    result_b = run_slice(DEFAULT_SIMULATION_CONFIG)
    assert result_a.days == result_b.days
    assert result_a.orders == result_b.orders


def test_seed_variation_changes_realization_but_preserves_invariants():
    result_a = run_slice(DEFAULT_SIMULATION_CONFIG)
    other_run = replace(DEFAULT_SIMULATION_CONFIG.run, seed=DEFAULT_SIMULATION_CONFIG.run.seed + 1)
    other_config = replace(DEFAULT_SIMULATION_CONFIG, run=other_run)
    result_b = run_slice(other_config)

    assert result_a.days != result_b.days

    for day in result_b.days:
        assert day.sales <= day.actual_demand
        assert day.sales <= day.opening_inventory
        assert day.closing_inventory == day.opening_inventory - day.sales + day.deliveries
        assert day.closing_inventory >= 0


def test_truncation_invariance_no_lookahead():
    """The acyclicity / no-lookahead rule, made falsifiable: truncating
    the simulation horizon must never change an earlier day's output,
    for any (store, SKU) pair.
    """
    full_result = run_slice(DEFAULT_SIMULATION_CONFIG, num_days=60)
    truncated_result = run_slice(DEFAULT_SIMULATION_CONFIG, num_days=30)

    num_pairs = _num_pairs(DEFAULT_SIMULATION_CONFIG)
    assert truncated_result.days == full_result.days[: 30 * num_pairs]

    cutoff = DEFAULT_SIMULATION_CONFIG.run.start_date
    full_orders_in_window = [o for o in full_result.orders if (o.order_date - cutoff).days < 30]
    assert truncated_result.orders == full_orders_in_window
