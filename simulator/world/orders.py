"""Document 9 -- ordering policy, actual order events, deliveries.

Periodic-review, order-up-to-level policy, per (store, SKU) pair. An
order placed for a pair on review day t depends only on that pair's
physical_inventory[t] (this day's opening inventory) and that pair's
own exogenous policy parameters -- never on inventory, sales, or
demand at any day later than t, and never on another pair's state (the
acyclicity / no-lookahead rule, Document 9).

Order quantity is rounded up to whole cases (units_per_case), per
Document 2's note that Document 9 needs this attribute for exactly
this purpose ("retailers commonly order and receive product in
whole-case increments even though they sell in eaches").

Order sizing here is deterministic (order_up_to - opening_inventory,
case-rounded). Document 9 requires actual orders not be mechanically
determined by policy, primarily so store_scale_class can't be
trivially recovered by comparing multiple stores' ordering behavior.
This slice does not yet reintroduce that variability -- an
intentionally simplified limitation, not a business decision.

Review timing is anchored per (store, SKU) pair (`review_anchor_day_index`
on OrderingPolicy), not to a single global calendar -- whether stores
sharing a retailer should share a review calendar is a business
question this slice deliberately does not decide.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from simulator.world.config import OrderingPolicy


@dataclass(frozen=True)
class Order:
    store_id: str
    sku_id: str
    order_date: date
    quantity: int
    lead_time_days: int
    expected_delivery_date: date


def is_review_day(day_index: int, policy: OrderingPolicy) -> bool:
    """Reviews occur every `policy.review_cadence_days`, first review
    at `policy.review_anchor_day_index`."""
    if day_index < policy.review_anchor_day_index:
        return False
    return (day_index - policy.review_anchor_day_index) % policy.review_cadence_days == 0


def place_order_if_due(
    store_id: str,
    sku_id: str,
    day_index: int,
    day: date,
    opening_inventory: int,
    policy: OrderingPolicy,
    units_per_case: int,
) -> Order | None:
    if not is_review_day(day_index, policy):
        return None
    gap = policy.order_up_to_level - opening_inventory
    if gap <= 0:
        return None
    cases = math.ceil(gap / units_per_case)
    quantity = cases * units_per_case
    return Order(
        store_id=store_id,
        sku_id=sku_id,
        order_date=day,
        quantity=quantity,
        lead_time_days=policy.lead_time_days,
        expected_delivery_date=day + timedelta(days=policy.lead_time_days),
    )
