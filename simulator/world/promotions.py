"""Document 10 -- Promotions & Events.

Promotion terms are Phase 1 exogenous "World / Parameters" -- decided
as part of building the world, before the days they affect, never
generated reactively (Document 10's "central risk" section). This
module fills exactly the two effects Document 10 approved:

    Promotion
       |--> demand-modifier lookup      (promotion_demand_phase_modifier)
       `--> pre-stocking ordering input (pre_stocking_order_up_to)

It never creates a new causal pathway to Sales or Inventory, and never
introduces a latent variable (no effective_price, promotion_demand,
promotion_inventory, excess_inventory, or similar) to make either
effect easier to compute. Consequences -- a real demand lift, an
inventory surplus left behind by an under-executed promotion -- must
emerge from the existing Demand -> Sales -> Inventory -> Orders chain
(demand.py, sales.py, inventory.py, orders.py), none of which this
module touches or imports.

Promotion != Assortment (Document 5). Nothing here validates or
assumes physical assortment. A promotion configured against a
store-SKU pair that isn't (or stops being) carried is a valid Phase 1
scenario; it simply never produces an effect, because clock.py only
ever calls into this module from inside its existing sell-eligibility
gate -- the same gate that already governs demand and order review
for every other reason a pair might not be sellable.

Pre-stocking reads only a promotion's *planned* terms
(scope/planned_start/planned_end/origin/discount_depth) and must never
read execution_state/actual_start/actual_end -- that boundary is what
keeps "pre-stocking responds to the plan, demand responds to
execution" (Document 10) causally real rather than incidental.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from simulator.world.config import PreStockingConfig, Promotion, PromotionDemandConfig


@dataclass(frozen=True)
class PromotionMagnitudes:
    """Drawn once per promotion, before the day loop, in fixed
    (config.promotions list) order -- never redrawn per day or per
    lookup. This is what keeps a promotion's effect deterministic
    given the seed and independent of how the world is traversed, the
    same discipline draw_potential_demand already established.
    """

    lift_log: float
    pre_phase_log: float
    post_phase_log: float


def draw_promotion_magnitudes(
    promotion: Promotion, config: PromotionDemandConfig, rng: np.random.Generator
) -> PromotionMagnitudes:
    lift_low, lift_high = config.lift_log_range
    base_lift = rng.uniform(lift_low, lift_high)
    if promotion.promotion_type == "PRICE_PROMOTION":
        # Confirmed (Document 10): discount_depth feeds only the
        # promotional modifier -- never Document 6's price-elasticity
        # term. This is the only place discount_depth enters the
        # model at all; draw_potential_demand never sees it.
        lift_log = base_lift + config.discount_sensitivity * promotion.discount_depth
    else:
        # NON_PRICE_EVENT: independent stochastic draw only, no
        # discount to scale from.
        lift_log = base_lift

    pre_low, pre_high = config.pre_phase_log_range
    pre_phase_log = rng.uniform(pre_low, pre_high)
    post_low, post_high = config.post_phase_log_range
    post_phase_log = rng.uniform(post_low, post_high)

    return PromotionMagnitudes(
        lift_log=lift_log, pre_phase_log=pre_phase_log, post_phase_log=post_phase_log
    )


@dataclass(frozen=True)
class PromotionPhaseEffect:
    phase: str | None  # "pre" | "lift" | "post" | None
    log_modifier: float


def promotion_demand_phase_modifier(
    promotion: Promotion, magnitudes: PromotionMagnitudes, day: date
) -> PromotionPhaseEffect:
    """Document 10, Effect 1: the demand modifier applies only to the
    *actual* execution window (never the planned one), and only when
    the promotion was executed at all.
    """
    if promotion.execution_state == "not_executed":
        return PromotionPhaseEffect(phase=None, log_modifier=0.0)

    actual_start = promotion.actual_start
    actual_end = promotion.actual_end
    pre_start = actual_start - timedelta(days=promotion.pre_phase_days)
    post_end = actual_end + timedelta(days=promotion.post_phase_days)

    if actual_start <= day <= actual_end:
        return PromotionPhaseEffect(phase="lift", log_modifier=magnitudes.lift_log)
    if pre_start <= day < actual_start:
        return PromotionPhaseEffect(phase="pre", log_modifier=magnitudes.pre_phase_log)
    if actual_end < day <= post_end:
        return PromotionPhaseEffect(phase="post", log_modifier=magnitudes.post_phase_log)
    return PromotionPhaseEffect(phase=None, log_modifier=0.0)


def pre_stocking_order_up_to(
    promotion: Promotion,
    day: date,
    base_order_up_to_level: int,
    config: PreStockingConfig,
) -> int:
    """Document 10, Effect 2: pre-stocking responds to the *planned*
    promotion -- reads only scope/planned_start/planned_end/origin
    (never execution_state/actual_start/actual_end) -- and only for
    NovaFoods-negotiated promotions, since a retailer-unilateral
    promotion is by definition unknown to NovaFoods in advance.

    Returns an adjusted order-up-to-level; the caller (clock.py) still
    passes it through the unmodified existing ordering mechanism
    (case rounding, lead time, and all) -- this function only computes
    an input to that mechanism, never an order or a delivery itself.
    """
    if promotion.origin != "NOVAFOODS_NEGOTIATED":
        return base_order_up_to_level

    window_start = promotion.planned_start - timedelta(days=config.lead_days)
    if window_start <= day < promotion.planned_start:
        return round(base_order_up_to_level * config.multiplier)
    return base_order_up_to_level
