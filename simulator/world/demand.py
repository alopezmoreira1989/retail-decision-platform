"""Document 6 -- potential demand baseline and actual daily demand.

Actual demand combines a shared per-(region, day) regional shock,
independent per-(store, SKU, day) idiosyncratic noise, and (Document
10) a promotional modifier, in log-space:

    log(actual_demand) = log(potential_demand) + log(seasonal_modifier)
                          + regional_shock + promotional_log_modifier
                          + idiosyncratic_noise

`promotional_log_modifier` is a precomputed scalar this module
receives, never something it looks up itself -- demand.py has no
awareness of the Promotion entity, no import from promotions.py, and
no read access to discount_depth. That separation is what keeps
Document 10's anti-double-counting rule structural rather than
conventional: `draw_potential_demand` below is completely unchanged by
this module's Vertical Slice #3 update, so discount_depth can never
reach the price/popularity-driven structural baseline it must stay
independent from.

This is the generalization of Document 6's confirmed statistical
property ("stores sharing the same region must receive correlated
demand shocks, while stores in different regions should have lower
correlation") -- stores in the same region see the identical
regional_shock value on a given day; stores in different regions see
independent draws. The shock is a fresh, independent draw per
(region, day) -- never autocorrelated across days, since Document 6
only requires same-day cross-store correlation, not a temporal
process. `region` never deterministically maps to a demand multiplier:
the shock is redrawn every day, so there is no fixed region -> demand
lookup an analytical model could trivially recover.

Only day-of-week seasonality is exercised; annual/holiday cyclicality
is omitted, since a 60-day window can't meaningfully demonstrate an
annual cycle.

Price is not a separate multiplier here (Document 6: baked into
potential demand once, via the product popularity factor -- never a
second, separate actual-demand multiplier). Since price isn't varied
across SKUs in this slice, it is absorbed into the product-popularity
draw rather than modeled as its own term -- a known limitation while
price has nothing to vary against, not a business decision.

`potential_demand` is the product of two independent, entity-level
latent quantities, not a single per-(store, SKU) pair draw:

    store_baseline[store]   -- drawn once per store (Document 4: "each
                                store gets its own individual baseline
                                demand level")
    sku_popularity[sku]     -- drawn once per SKU (Document 6: "each
                                SKU carries its own individual
                                popularity factor")
    potential_demand[store, sku] = store_baseline[store] * sku_popularity[sku]

Each is drawn exactly once, before the day loop, in a fixed
(config.stores / config.skus) order -- see clock.py. No third,
per-pair random term is introduced: pair-level heterogeneity still
comes from the daily idiosyncratic-noise draw in draw_actual_demand,
plus the multiplicative interaction of two independent per-entity
values, which already differentiates every pair without needing its
own draw.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from simulator.world.config import DemandConfig
from simulator.world.entities import Store


def draw_store_baseline(
    demand_config: DemandConfig, store: Store, rng: np.random.Generator
) -> float:
    """Document 4: each store's own individual baseline demand level,
    drawn once per store -- a structural, relatively stable quantity.
    Must happen before any day-loop RNG usage, in a fixed store order,
    so it can never depend on the simulation horizon length (see
    clock.py's truncation-invariance discipline).
    """
    low, high = demand_config.store_baseline_range_by_tier[store.store_scale_class]
    return rng.uniform(low, high)


def draw_sku_popularity(demand_config: DemandConfig, rng: np.random.Generator) -> float:
    """Document 6: each SKU's own individual popularity factor, drawn
    once per SKU -- constant across every store that carries it. Must
    happen before any day-loop RNG usage, in a fixed SKU order, for
    the same truncation-invariance reason as draw_store_baseline.
    """
    pop_low, pop_high = demand_config.product_popularity_range
    return rng.uniform(pop_low, pop_high)


def combine_potential_demand(store_baseline: float, sku_popularity: float) -> float:
    """Document 4 + Document 6: potential demand for a (store, SKU)
    pair is the product of that store's baseline and that SKU's
    popularity -- a pure lookup/multiply, no RNG involved. Both inputs
    were already drawn once, per entity, before the day loop.
    """
    return store_baseline * sku_popularity


def draw_regional_shocks(
    regions: list[str], demand_config: DemandConfig, rng: np.random.Generator
) -> dict[str, float]:
    """One fresh Normal(0, regional_shock_sigma) draw per region, in
    the fixed order `regions` is given in. Called once per day, before
    any per-pair idiosyncratic draw -- see clock.py.
    """
    return {
        region: float(rng.normal(0.0, demand_config.regional_shock_sigma)) for region in regions
    }


def draw_actual_demand(
    potential_demand: float,
    day: date,
    demand_config: DemandConfig,
    regional_shock: float,
    promotional_log_modifier: float,
    rng: np.random.Generator,
) -> int:
    """Document 6 + Document 10: actual demand = potential demand x
    seasonal modifier x regional shock x promotional modifier x
    idiosyncratic noise, combined in log-space.

    Exactly one scalar RNG draw (the idiosyncratic component) per
    call, so that truncating the simulation horizon can never change
    an earlier day's draw. `promotional_log_modifier` is not drawn
    here -- it is computed once per promotion, before the day loop, by
    promotions.draw_promotion_magnitudes (see clock.py), and looked up
    per day by promotions.promotion_demand_phase_modifier.
    """
    seasonal_modifier = demand_config.weekday_seasonal_modifiers[day.weekday()]
    idiosyncratic_noise = rng.normal(0.0, demand_config.idiosyncratic_noise_sigma)
    log_demand = (
        math.log(potential_demand)
        + math.log(seasonal_modifier)
        + regional_shock
        + promotional_log_modifier
        + idiosyncratic_noise
    )
    return max(0, round(math.exp(log_demand)))
