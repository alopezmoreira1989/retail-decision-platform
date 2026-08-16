"""Invariant, determinism, and no-lookahead tests for Vertical Slice #3
(N stores x N SKUs, explicit physical assortment, regional demand
correlation, Document 10 promotions).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from simulator.world.assortment import is_available
from simulator.world.clock import run_slice
from simulator.world.config import DEFAULT_SIMULATION_CONFIG as CONFIG
from simulator.world.config import AssortmentWindow, Promotion
from simulator.world.demand import draw_actual_demand, draw_regional_shocks
from simulator.world.promotions import pre_stocking_order_up_to
from simulator.world.sales import compute_sales

NEVER_CARRIED_PAIR = ("STORE-001", "SKU-003")
INELIGIBLE_SKU = "SKU-004"
TEMPORAL_GAP_PAIR = ("STORE-001", "SKU-002")

EXECUTED_PROMO_PAIR = ("STORE-003", "SKU-001")  # PROMO-003
NOT_EXECUTED_PROMO_PAIR = ("STORE-002", "SKU-001")  # PROMO-002
PARTIALLY_EXECUTED_PROMO_PAIR = ("STORE-001", "SKU-001")  # PROMO-001
RETAILER_UNILATERAL_PAIR = ("STORE-003", "SKU-003")  # PROMO-004
NON_ASSORTED_PROMO_PAIR = ("STORE-001", "SKU-003")  # PROMO-005


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


def _promotion(promotion_id: str) -> Promotion:
    return next(p for p in CONFIG.promotions if p.promotion_id == promotion_id)


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
    result = run_slice(CONFIG)
    assert len(result.stores) == len(CONFIG.stores) > 1
    assert len(result.skus) == len(CONFIG.skus) > 1

    configured_store_ids = {sc.store_id for sc in CONFIG.stores}
    configured_sku_ids = {kc.sku_id for kc in CONFIG.skus}
    assert {s.store_id for s in result.stores} == configured_store_ids
    assert {k.sku_id for k in result.skus} == configured_sku_ids

    # every (store, SKU) pair in the tracking universe is exercised,
    # whether or not it is ever physically assorted
    observed_pairs = {(d.store_id, d.sku_id) for d in result.days}
    assert observed_pairs == set(CONFIG.ordering_policies.keys())
    assert len(observed_pairs) == _num_pairs(CONFIG)


# ---------------------------------------------------------------------
# Distribution eligibility (Document 5, Layer 2)
# ---------------------------------------------------------------------


def test_distribution_ineligibility_validation_rejects_contradiction():
    """SimulationConfig must refuse to construct if a distribution-
    ineligible SKU has any physical assortment window anywhere.
    """
    bad_assortment = dict(CONFIG.assortment)
    bad_assortment[("STORE-002", INELIGIBLE_SKU)] = [
        AssortmentWindow(effective_from=CONFIG.run.start_date, effective_to=None)
    ]
    with pytest.raises(ValueError, match="distribution-ineligible"):
        replace(CONFIG, assortment=bad_assortment)


def test_distribution_ineligible_sku_never_carried_by_any_store():
    result = run_slice(CONFIG)
    assert CONFIG.distribution_eligibility[INELIGIBLE_SKU] is False
    for day in result.days:
        if day.sku_id == INELIGIBLE_SKU:
            assert day.physical_assortment is False
            assert day.sell_eligible is False
            assert day.actual_demand == 0
            assert day.sales == 0
            assert day.order_placed_quantity == 0


# ---------------------------------------------------------------------
# Physical assortment (Document 5, Layer 3) -- explicit config (Option A)
# ---------------------------------------------------------------------


def test_assortment_windows_do_not_overlap_per_pair():
    for windows in CONFIG.assortment.values():
        sorted_windows = sorted(windows, key=lambda w: w.effective_from)
        for earlier, later in zip(sorted_windows, sorted_windows[1:], strict=False):
            if earlier.effective_to is not None:
                assert earlier.effective_to < later.effective_from


def test_never_carried_pair_has_no_sales_demand_or_orders():
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    rows = by_pair[NEVER_CARRIED_PAIR]
    assert len(rows) == CONFIG.run.num_days
    for row in rows:
        assert row.physical_assortment is False
        assert row.sell_eligible is False
        assert row.available is False
        assert row.actual_demand == 0
        assert row.sales == 0
        assert row.order_placed_quantity == 0
        assert row.deliveries == 0


def test_temporal_assortment_gap_behaves_correctly():
    """Document 5's "leaving and returning" case: carried, then a gap,
    then carried again -- just a second row, no new lifecycle state.
    """
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    rows = by_pair[TEMPORAL_GAP_PAIR]
    start = CONFIG.run.start_date

    carried_before_gap = [r for r in rows if r.date <= start + timedelta(days=29)]
    gap = [r for r in rows if start + timedelta(days=30) <= r.date <= start + timedelta(days=39)]
    carried_after_gap = [r for r in rows if r.date >= start + timedelta(days=40)]

    assert carried_before_gap and gap and carried_after_gap
    assert all(r.sell_eligible for r in carried_before_gap)
    assert all(not r.sell_eligible for r in gap)
    assert all(r.actual_demand == 0 and r.sales == 0 for r in gap)
    assert all(r.sell_eligible for r in carried_after_gap)


def test_orders_never_placed_when_not_sell_eligible():
    """The order gate: clock.py must never call orders.place_order_if_due
    for a pair that is not sell-eligible that day (neither because it
    was never carried, nor because it is currently in an assortment
    gap).
    """
    result = run_slice(CONFIG)
    for day in result.days:
        if not day.sell_eligible:
            assert day.order_placed_quantity == 0


# ---------------------------------------------------------------------
# Promotions (Document 10) -- structural validation
# ---------------------------------------------------------------------


def test_promotion_validation_rejects_bad_dates():
    with pytest.raises(ValueError, match="planned_start"):
        Promotion(
            promotion_id="BAD",
            store_id="STORE-001",
            sku_id="SKU-001",
            promotion_type="PRICE_PROMOTION",
            discount_depth=0.1,
            origin="NOVAFOODS_NEGOTIATED",
            planned_start=date(2026, 2, 1),
            planned_end=date(2026, 1, 1),
            execution_state="not_executed",
            actual_start=None,
            actual_end=None,
            pre_phase_days=3,
            post_phase_days=5,
        )


def test_promotion_validation_non_price_event_rejects_discount():
    with pytest.raises(ValueError, match="NON_PRICE_EVENT"):
        Promotion(
            promotion_id="BAD",
            store_id="STORE-001",
            sku_id="SKU-001",
            promotion_type="NON_PRICE_EVENT",
            discount_depth=0.1,
            origin="RETAILER_UNILATERAL",
            planned_start=date(2026, 1, 1),
            planned_end=date(2026, 1, 10),
            execution_state="not_executed",
            actual_start=None,
            actual_end=None,
            pre_phase_days=3,
            post_phase_days=5,
        )


def test_promotion_validation_price_promotion_requires_discount():
    with pytest.raises(ValueError, match="PRICE_PROMOTION"):
        Promotion(
            promotion_id="BAD",
            store_id="STORE-001",
            sku_id="SKU-001",
            promotion_type="PRICE_PROMOTION",
            discount_depth=None,
            origin="NOVAFOODS_NEGOTIATED",
            planned_start=date(2026, 1, 1),
            planned_end=date(2026, 1, 10),
            execution_state="not_executed",
            actual_start=None,
            actual_end=None,
            pre_phase_days=3,
            post_phase_days=5,
        )


def test_promotion_validation_not_executed_rejects_actual_dates():
    with pytest.raises(ValueError, match="not_executed"):
        Promotion(
            promotion_id="BAD",
            store_id="STORE-001",
            sku_id="SKU-001",
            promotion_type="PRICE_PROMOTION",
            discount_depth=0.1,
            origin="NOVAFOODS_NEGOTIATED",
            planned_start=date(2026, 1, 1),
            planned_end=date(2026, 1, 10),
            execution_state="not_executed",
            actual_start=date(2026, 1, 1),
            actual_end=date(2026, 1, 10),
            pre_phase_days=3,
            post_phase_days=5,
        )


def test_promotion_validation_executed_requires_actual_dates():
    with pytest.raises(ValueError, match="requires actual_start"):
        Promotion(
            promotion_id="BAD",
            store_id="STORE-001",
            sku_id="SKU-001",
            promotion_type="PRICE_PROMOTION",
            discount_depth=0.1,
            origin="NOVAFOODS_NEGOTIATED",
            planned_start=date(2026, 1, 1),
            planned_end=date(2026, 1, 10),
            execution_state="executed",
            actual_start=None,
            actual_end=None,
            pre_phase_days=3,
            post_phase_days=5,
        )


def test_promotion_validation_executed_must_mirror_planned():
    with pytest.raises(ValueError, match="mirror the planned dates"):
        Promotion(
            promotion_id="BAD",
            store_id="STORE-001",
            sku_id="SKU-001",
            promotion_type="PRICE_PROMOTION",
            discount_depth=0.1,
            origin="NOVAFOODS_NEGOTIATED",
            planned_start=date(2026, 1, 1),
            planned_end=date(2026, 1, 10),
            execution_state="executed",
            actual_start=date(2026, 1, 2),  # doesn't mirror planned_start
            actual_end=date(2026, 1, 10),
            pre_phase_days=3,
            post_phase_days=5,
        )


def test_overlapping_promotions_on_same_pair_rejected():
    """Slice limitation, not a Ground Truth rule: at most one
    promotion per (store, SKU) pair.
    """
    duplicate = replace(_promotion("PROMO-001"), promotion_id="PROMO-001-DUP")
    with pytest.raises(ValueError, match="More than one promotion"):
        replace(CONFIG, promotions=[*CONFIG.promotions, duplicate])


# ---------------------------------------------------------------------
# Promotions -- execution vs. plan (Document 10, Effect 1)
# ---------------------------------------------------------------------


def test_executed_promotion_lift_applies_only_during_actual_window():
    promo = _promotion("PROMO-003")
    result = run_slice(CONFIG)
    rows = _by_pair(result.days)[EXECUTED_PROMO_PAIR]

    for row in rows:
        if promo.actual_start <= row.date <= promo.actual_end:
            assert row.promotion_phase == "lift"
            assert row.promotion_log_modifier > 0
        elif (
            promo.actual_start - timedelta(days=promo.pre_phase_days)
            <= row.date
            < promo.actual_start
        ):
            assert row.promotion_phase == "pre"
            assert row.promotion_log_modifier < 0
        elif (
            promo.actual_end < row.date <= promo.actual_end + timedelta(days=promo.post_phase_days)
        ):
            assert row.promotion_phase == "post"
            assert row.promotion_log_modifier < 0
        else:
            assert row.promotion_phase is None
            assert row.promotion_log_modifier == 0.0


def test_not_executed_promotion_produces_no_demand_lift_ever():
    """A planned-but-not-executed promotion must never affect demand,
    for its entire configured life -- Document 10, Effect 1.
    """
    result = run_slice(CONFIG)
    rows = _by_pair(result.days)[NOT_EXECUTED_PROMO_PAIR]
    for row in rows:
        assert row.promotion_id == "PROMO-002"
        assert row.promotion_phase is None
        assert row.promotion_log_modifier == 0.0


def test_partial_execution_respects_actual_not_planned_dates():
    """Document 10's own illustrative scenario: a late start means no
    lift for the days between the plan and the actual start, even
    though the promotion was "supposed to" already be running.
    """
    promo = _promotion("PROMO-001")
    assert promo.actual_start > promo.planned_start  # started late
    result = run_slice(CONFIG)
    rows_by_date = {r.date: r for r in _by_pair(result.days)[PARTIALLY_EXECUTED_PROMO_PAIR]}

    late_start_gap_day = promo.planned_start  # planned to have started; didn't yet
    assert rows_by_date[late_start_gap_day].promotion_phase != "lift"
    assert rows_by_date[promo.actual_start].promotion_phase == "lift"


# ---------------------------------------------------------------------
# Promotions -- discount_depth anti-double-counting (Document 10)
# ---------------------------------------------------------------------


def test_discount_depth_never_affects_potential_demand():
    """Regression guard: discount_depth must never reach
    draw_potential_demand / Document 6's price-elasticity term. Removing
    all promotions must not change any pair's potential_demand.
    """
    result_with_promotions = run_slice(CONFIG)
    config_without_promotions = replace(CONFIG, promotions=[])
    result_without_promotions = run_slice(config_without_promotions)

    with_by_pair = _by_pair(result_with_promotions.days)
    without_by_pair = _by_pair(result_without_promotions.days)
    for key in CONFIG.ordering_policies:
        assert with_by_pair[key][0].potential_demand == without_by_pair[key][0].potential_demand


# ---------------------------------------------------------------------
# Promotions -- pre-stocking (Document 10, Effect 2) and knowledge gating
# ---------------------------------------------------------------------


def test_prestocking_boost_applies_only_within_lead_window():
    promo = _promotion("PROMO-003")
    base_level = 150

    before_window = promo.planned_start - timedelta(days=CONFIG.pre_stocking.lead_days + 1)
    assert (
        pre_stocking_order_up_to(promo, before_window, base_level, CONFIG.pre_stocking)
        == base_level
    )

    inside_window = promo.planned_start - timedelta(days=1)
    boosted = pre_stocking_order_up_to(promo, inside_window, base_level, CONFIG.pre_stocking)
    assert boosted > base_level
    assert boosted == round(base_level * CONFIG.pre_stocking.multiplier)

    on_planned_start = promo.planned_start
    assert (
        pre_stocking_order_up_to(promo, on_planned_start, base_level, CONFIG.pre_stocking)
        == base_level
    )


def test_retailer_unilateral_promotion_never_boosts_prestocking():
    """NovaFoods cannot pre-stock for a promotion it doesn't know about
    in advance -- origin gates pre-stocking, not execution or outcome.
    """
    promo = _promotion("PROMO-004")
    assert promo.origin == "RETAILER_UNILATERAL"
    base_level = 90
    inside_what_would_be_the_window = promo.planned_start - timedelta(days=1)
    assert (
        pre_stocking_order_up_to(
            promo, inside_what_would_be_the_window, base_level, CONFIG.pre_stocking
        )
        == base_level
    )


def test_known_promotion_prestocking_fires_even_when_not_executed():
    """Case A: pre-stocking responds to the plan, not to execution --
    a real order is placed ahead of a promotion that never actually runs.
    """
    result = run_slice(CONFIG)
    promo = _promotion("PROMO-002")
    window_start_index = (
        promo.planned_start - CONFIG.run.start_date
    ).days - CONFIG.pre_stocking.lead_days
    window_end_index = (promo.planned_start - CONFIG.run.start_date).days
    rows = _by_pair(result.days)[NOT_EXECUTED_PROMO_PAIR]
    orders_in_window = [
        r
        for r in rows
        if window_start_index <= r.day_index < window_end_index and r.order_placed_quantity > 0
    ]
    assert orders_in_window  # pre-stocking really happened
    # and yet it produced zero demand lift (already asserted separately)


def test_retailer_unilateral_executed_promotion_lifts_demand_without_prestocking():
    """Case C: real execution still produces a real demand lift, even
    though NovaFoods never knew about the promotion in advance.
    """
    result = run_slice(CONFIG)
    promo = _promotion("PROMO-004")
    rows = _by_pair(result.days)[RETAILER_UNILATERAL_PAIR]
    assert any(
        r.promotion_phase == "lift"
        for r in rows
        if promo.actual_start <= r.date <= promo.actual_end
    )


# ---------------------------------------------------------------------
# Promotions -- interaction with assortment (Document 5 vs. Document 10)
# ---------------------------------------------------------------------


def test_promotion_on_non_assorted_pair_has_no_effect():
    """Promotion != Assortment. A promotion configured on a pair that
    is never physically assorted is a valid Phase 1 scenario -- it
    must never create sell-eligibility, demand, sales, or orders.
    """
    result = run_slice(CONFIG)
    rows = _by_pair(result.days)[NON_ASSORTED_PROMO_PAIR]
    assert len(rows) == CONFIG.run.num_days
    for row in rows:
        assert row.promotion_id == "PROMO-005"  # the promotion "exists" for this pair...
        assert row.sell_eligible is False  # ...but assortment still governs everything
        assert row.promotion_phase is None
        assert row.actual_demand == 0
        assert row.sales == 0
        assert row.order_placed_quantity == 0


# ---------------------------------------------------------------------
# Promotions -- no-lookahead
# ---------------------------------------------------------------------


def test_future_promotion_does_not_affect_earlier_days():
    """Moving a known promotion's dates further into the future must
    never change any day generated before its (new, later)
    pre-stocking window -- and must not affect any other pair at all.
    """
    original_promo = _promotion("PROMO-003")
    shift = timedelta(days=100)
    shifted_promo = replace(
        original_promo,
        planned_start=original_promo.planned_start + shift,
        planned_end=original_promo.planned_end + shift,
        actual_start=original_promo.actual_start + shift,
        actual_end=original_promo.actual_end + shift,
    )
    shifted_promotions = [
        shifted_promo if p.promotion_id == "PROMO-003" else p for p in CONFIG.promotions
    ]
    shifted_config = replace(CONFIG, promotions=shifted_promotions)

    original_result = run_slice(CONFIG)
    shifted_result = run_slice(shifted_config)

    original_by_pair = _by_pair(original_result.days)
    shifted_by_pair = _by_pair(shifted_result.days)

    # every other pair is completely unaffected by shifting PROMO-003
    for key in CONFIG.ordering_policies:
        if key != EXECUTED_PROMO_PAIR:
            assert original_by_pair[key] == shifted_by_pair[key]

    # the target pair matches before the (original) pre-stocking window starts...
    window_start_index = (
        original_promo.planned_start - CONFIG.run.start_date
    ).days - CONFIG.pre_stocking.lead_days
    original_rows = original_by_pair[EXECUTED_PROMO_PAIR]
    shifted_rows = shifted_by_pair[EXECUTED_PROMO_PAIR]
    for original_row, shifted_row in zip(original_rows, shifted_rows, strict=True):
        if original_row.day_index < window_start_index:
            assert original_row == shifted_row

    # ...and genuinely diverges afterward, proving this isn't a vacuous check
    assert any(
        original_row != shifted_row
        for original_row, shifted_row in zip(original_rows, shifted_rows, strict=True)
        if original_row.day_index >= window_start_index
    )


# ---------------------------------------------------------------------
# SKU popularity / store baseline -- entity-level, not per-pair
# (World Variety & Lifecycle checkpoint)
# ---------------------------------------------------------------------


def test_sku_popularity_ratio_constant_across_stores():
    """sku_popularity[sku] is shared across every store that carries
    it: the ratio of potential_demand between two stores must be
    identical for every SKU both stores carry -- store_baseline only
    cancels out of that ratio if popularity doesn't vary by pair.
    """
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    shared_skus = ["SKU-001", "SKU-003"]  # both carried by STORE-002 and STORE-004
    ratios = [
        by_pair[("STORE-002", sku_id)][0].potential_demand
        / by_pair[("STORE-004", sku_id)][0].potential_demand
        for sku_id in shared_skus
    ]
    assert ratios[0] == pytest.approx(ratios[1], rel=1e-9)


def test_store_baseline_ratio_constant_across_skus():
    """store_baseline[store] is shared across every SKU that store
    carries: the ratio of potential_demand between two SKUs must be
    identical at every store that carries both.
    """
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    stores_sharing_both = ["STORE-002", "STORE-004"]  # both carry SKU-001 and SKU-003
    ratios = [
        by_pair[(store_id, "SKU-001")][0].potential_demand
        / by_pair[(store_id, "SKU-003")][0].potential_demand
        for store_id in stores_sharing_both
    ]
    assert ratios[0] == pytest.approx(ratios[1], rel=1e-9)


def test_different_skus_and_stores_can_have_different_potential_demand():
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    values = {
        by_pair[("STORE-002", "SKU-001")][0].potential_demand,
        by_pair[("STORE-002", "SKU-003")][0].potential_demand,
        by_pair[("STORE-004", "SKU-001")][0].potential_demand,
    }
    assert len(values) > 1  # not everything collapsed to one shared value


# ---------------------------------------------------------------------
# Product lifecycle (Document 2) -- SKU-003, ACTIVE -> DISCONTINUED day 45
# ---------------------------------------------------------------------

DISCONTINUED_SKU = "SKU-003"
DISCONTINUATION_DAY_INDEX = 54


def _stores_carrying(sku_id: str) -> list[str]:
    return [
        store_id
        for (store_id, s_id), windows in CONFIG.assortment.items()
        if s_id == sku_id and windows
    ]


def test_discontinued_sku_becomes_non_sell_eligible_at_every_carrying_store():
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    carrying_stores = _stores_carrying(DISCONTINUED_SKU)
    assert len(carrying_stores) > 1  # exercising the catalog-wide, multi-store pattern
    for store_id in carrying_stores:
        for row in by_pair[(store_id, DISCONTINUED_SKU)]:
            if row.day_index < DISCONTINUATION_DAY_INDEX:
                assert row.sku_lifecycle_state == "ACTIVE"
            else:
                assert row.sku_lifecycle_state == "DISCONTINUED"
                assert row.sell_eligible is False
                assert row.actual_demand == 0
                assert row.sales == 0
                assert row.order_placed_quantity == 0


def test_discontinuation_does_not_change_physical_assortment():
    result = run_slice(CONFIG)
    rows = _by_pair(result.days)[("STORE-003", DISCONTINUED_SKU)]
    assert all(row.physical_assortment for row in rows)


def test_discontinuation_does_not_affect_other_skus_at_the_same_store():
    result = run_slice(CONFIG)
    rows = _by_pair(result.days)[("STORE-003", "SKU-001")]
    assert all(row.sku_lifecycle_state == "ACTIVE" for row in rows)


def test_in_transit_delivery_still_arrives_after_discontinuation():
    """The decision this checkpoint closed explicitly: an order placed
    before discontinuation is not cancelled -- its delivery still lands
    on schedule, even after the SKU has become DISCONTINUED.
    """
    result = run_slice(CONFIG)
    rows_by_index = {r.day_index: r for r in _by_pair(result.days)[("STORE-004", DISCONTINUED_SKU)]}
    delivery_day = 57  # see the discontinued_on comment on SKU-003 in config.py
    assert rows_by_index[delivery_day].sku_lifecycle_state == "DISCONTINUED"
    assert rows_by_index[delivery_day].deliveries > 0


# ---------------------------------------------------------------------
# Store lifecycle (Document 4) -- STORE-006, OPEN -> TEMPORARILY_CLOSED
# -> OPEN, days 20-27
# ---------------------------------------------------------------------

CLOSED_STORE = "STORE-006"
CLOSURE_START_INDEX = 15
CLOSURE_END_INDEX = 22


def _skus_carried_by(store_id: str) -> list[str]:
    return [
        sku_id
        for (s_id, sku_id), windows in CONFIG.assortment.items()
        if s_id == store_id and windows
    ]


def test_store_closure_affects_every_carried_sku_simultaneously():
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    carried_skus = _skus_carried_by(CLOSED_STORE)
    assert carried_skus
    for sku_id in carried_skus:
        for row in by_pair[(CLOSED_STORE, sku_id)]:
            if CLOSURE_START_INDEX <= row.day_index <= CLOSURE_END_INDEX:
                assert row.store_lifecycle_state == "TEMPORARILY_CLOSED"
                assert row.sell_eligible is False
                assert row.actual_demand == 0
                assert row.sales == 0
                assert row.order_placed_quantity == 0
            else:
                assert row.store_lifecycle_state == "OPEN"


def test_store_closure_does_not_affect_other_stores():
    result = run_slice(CONFIG)
    rows = _by_pair(result.days)[("STORE-001", "SKU-001")]
    assert all(row.store_lifecycle_state == "OPEN" for row in rows)


def test_store_identity_persists_after_reopening():
    result = run_slice(CONFIG)
    store = next(s for s in result.stores if s.store_id == CLOSED_STORE)
    assert store.store_scale_class == 1
    assert store.format == "Discount"
    assert store.region == "Central"

    rows = _by_pair(result.days)[(CLOSED_STORE, "SKU-001")]
    after_reopening = [r for r in rows if r.day_index > CLOSURE_END_INDEX]
    assert after_reopening
    assert any(r.sell_eligible for r in after_reopening)


def test_in_transit_delivery_still_arrives_during_store_closure():
    result = run_slice(CONFIG)
    rows_by_index = {r.day_index: r for r in _by_pair(result.days)[(CLOSED_STORE, "SKU-001")]}
    delivery_day = 16  # see the closure comment on STORE-006 in config.py
    assert rows_by_index[delivery_day].store_lifecycle_state == "TEMPORARILY_CLOSED"
    assert rows_by_index[delivery_day].deliveries > 0


# ---------------------------------------------------------------------
# Regional demand correlation -- mechanism-level, not a statistical
# result demanded from a small sample.
# ---------------------------------------------------------------------


def test_regional_shocks_one_per_region_in_fixed_order():
    rng = np.random.default_rng(123)
    shocks = draw_regional_shocks(["North", "South"], CONFIG.demand, rng)
    assert set(shocks.keys()) == {"North", "South"}
    assert shocks["North"] != shocks["South"]


def test_regional_shocks_deterministic_given_same_rng_state():
    shocks_a = draw_regional_shocks(CONFIG.regions, CONFIG.demand, np.random.default_rng(7))
    shocks_b = draw_regional_shocks(CONFIG.regions, CONFIG.demand, np.random.default_rng(7))
    assert shocks_a == shocks_b


def test_regional_shocks_not_autocorrelated_across_days():
    """Region does not deterministically determine demand: two
    successive draws from the same stream (i.e. two different days)
    must differ.
    """
    rng = np.random.default_rng(99)
    shocks_day1 = draw_regional_shocks(CONFIG.regions, CONFIG.demand, rng)
    shocks_day2 = draw_regional_shocks(CONFIG.regions, CONFIG.demand, rng)
    assert shocks_day1 != shocks_day2


def test_actual_demand_applies_shared_regional_shock_identically():
    """Same potential demand + same regional shock + zero idiosyncratic
    variance must produce identical realized demand -- proving the
    regional shock is a genuine shared multiplier, not something that
    silently varies per call.
    """
    zero_idio_demand_config = replace(CONFIG.demand, idiosyncratic_noise_sigma=0.0)
    a_monday = date(2026, 1, 5)

    demand_a = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.3,
        promotional_log_modifier=0.0,
        rng=np.random.default_rng(1),
    )
    demand_b = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.3,
        promotional_log_modifier=0.0,
        rng=np.random.default_rng(1),
    )
    assert demand_a == demand_b


def test_actual_demand_changes_with_regional_shock():
    zero_idio_demand_config = replace(CONFIG.demand, idiosyncratic_noise_sigma=0.0)
    a_monday = date(2026, 1, 5)

    higher = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.5,
        promotional_log_modifier=0.0,
        rng=np.random.default_rng(1),
    )
    lower = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=-0.5,
        promotional_log_modifier=0.0,
        rng=np.random.default_rng(1),
    )
    assert higher > lower


def test_actual_demand_changes_with_promotional_modifier():
    zero_idio_demand_config = replace(CONFIG.demand, idiosyncratic_noise_sigma=0.0)
    a_monday = date(2026, 1, 5)

    with_lift = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.0,
        promotional_log_modifier=0.4,
        rng=np.random.default_rng(1),
    )
    without_lift = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=zero_idio_demand_config,
        regional_shock=0.0,
        promotional_log_modifier=0.0,
        rng=np.random.default_rng(1),
    )
    assert with_lift > without_lift


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
        demand_config=CONFIG.demand,
        regional_shock=0.0,
        promotional_log_modifier=0.0,
        rng=rng,
    )
    demand_b = draw_actual_demand(
        potential_demand=100.0,
        day=a_monday,
        demand_config=CONFIG.demand,
        regional_shock=0.0,
        promotional_log_modifier=0.0,
        rng=rng,
    )
    assert demand_a != demand_b


# ---------------------------------------------------------------------
# Per-row invariants across every generated (day, store, SKU) row
# ---------------------------------------------------------------------


def test_no_sales_outside_assortment_or_eligibility():
    result = run_slice(CONFIG)
    for day in result.days:
        if not day.physical_assortment:
            assert day.sales == 0
        if not day.sell_eligible:
            assert day.sales == 0
            assert day.actual_demand == 0


def test_sales_never_exceed_demand():
    result = run_slice(CONFIG)
    for day in result.days:
        assert day.sales <= day.actual_demand


def test_sales_never_exceed_opening_inventory():
    result = run_slice(CONFIG)
    for day in result.days:
        assert day.sales <= day.opening_inventory


def test_inventory_conservation():
    result = run_slice(CONFIG)
    for day in result.days:
        assert day.closing_inventory == day.opening_inventory - day.sales + day.deliveries


def test_inventory_never_negative():
    result = run_slice(CONFIG)
    for day in result.days:
        assert day.opening_inventory >= 0
        assert day.closing_inventory >= 0


def test_slice_stockout_flags_agree_with_unmet_demand():
    result = run_slice(CONFIG)
    for day in result.days:
        assert day.stockout == (day.unmet_demand > 0)
    assert any(
        day.opening_inventory > 0 and day.unmet_demand > 0 and day.stockout for day in result.days
    )


def test_slice_available_flags_agree_with_definition():
    result = run_slice(CONFIG)
    for day in result.days:
        assert day.available == (day.sell_eligible and day.opening_inventory > 0)
    assert any(not day.available and day.opening_inventory == 0 for day in result.days)


# ---------------------------------------------------------------------
# Pair-aware invariants (per (store, SKU) relationship)
# ---------------------------------------------------------------------


def test_opening_inventory_carries_forward_per_pair():
    result = run_slice(CONFIG)
    for rows in _by_pair(result.days).values():
        for prev_day, next_day in zip(rows, rows[1:], strict=False):
            assert next_day.opening_inventory == prev_day.closing_inventory


def test_initial_inventory_is_a_fixed_parameter_not_derived():
    result = run_slice(CONFIG)
    by_pair = _by_pair(result.days)
    for key, expected_initial in CONFIG.initial_inventory.items():
        assert by_pair[key][0].opening_inventory == expected_initial

    # changing demand parameters must not change any pair's Day 1
    # opening inventory -- it is a fixed slice parameter, never derived
    # from any demand or sales output.
    altered_demand = replace(CONFIG.demand, idiosyncratic_noise_sigma=0.9)
    altered_run = replace(CONFIG.run, seed=CONFIG.run.seed + 1)
    altered_config = replace(CONFIG, demand=altered_demand, run=altered_run)
    altered_result = run_slice(altered_config)
    altered_by_pair = _by_pair(altered_result.days)
    for key, expected_initial in CONFIG.initial_inventory.items():
        assert altered_by_pair[key][0].opening_inventory == expected_initial


def test_orders_placed_only_on_that_pairs_review_days():
    result = run_slice(CONFIG)
    for day in result.days:
        if day.order_placed_quantity > 0:
            policy = CONFIG.ordering_policies[(day.store_id, day.sku_id)]
            assert day.day_index >= policy.review_anchor_day_index
            assert (
                day.day_index - policy.review_anchor_day_index
            ) % policy.review_cadence_days == 0


def test_orders_do_not_affect_same_day_inventory():
    result = run_slice(CONFIG)
    for order in result.orders:
        assert order.lead_time_days > 0
        order_day_index = (order.order_date - CONFIG.run.start_date).days
        delivery_day_index = order_day_index + order.lead_time_days
        assert delivery_day_index != order_day_index


def test_delivery_respects_lead_time_per_pair():
    result = run_slice(CONFIG)
    rows_by_key = {(d.day_index, d.store_id, d.sku_id): d for d in result.days}
    for order in result.orders:
        order_day_index = (order.order_date - CONFIG.run.start_date).days
        delivery_day_index = order_day_index + order.lead_time_days
        lookup_key = (delivery_day_index, order.store_id, order.sku_id)
        if lookup_key in rows_by_key:
            assert rows_by_key[lookup_key].deliveries == order.quantity


# ---------------------------------------------------------------------
# Determinism and no-lookahead
# ---------------------------------------------------------------------


def test_determinism_same_seed_identical_output():
    result_a = run_slice(CONFIG)
    result_b = run_slice(CONFIG)
    assert result_a.days == result_b.days
    assert result_a.orders == result_b.orders


def test_seed_variation_changes_realization_but_preserves_invariants():
    result_a = run_slice(CONFIG)
    other_run = replace(CONFIG.run, seed=CONFIG.run.seed + 1)
    other_config = replace(CONFIG, run=other_run)
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
    for any (store, SKU) pair -- including pairs whose assortment
    changes partway through the window, and pairs affected by a
    promotion.
    """
    full_result = run_slice(CONFIG, num_days=60)
    truncated_result = run_slice(CONFIG, num_days=30)

    num_pairs = _num_pairs(CONFIG)
    assert truncated_result.days == full_result.days[: 30 * num_pairs]

    cutoff = CONFIG.run.start_date
    full_orders_in_window = [o for o in full_result.orders if (o.order_date - cutoff).days < 30]
    assert truncated_result.orders == full_orders_in_window
