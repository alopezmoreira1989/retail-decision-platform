"""Document 6 -- potential demand baseline and actual daily demand.

Actual demand combines a shared per-(region, day) regional shock with
independent per-(store, SKU, day) idiosyncratic noise, in log-space:

    log(actual_demand) = log(potential_demand) + log(seasonal_modifier)
                          + regional_shock + idiosyncratic_noise

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

The promotional modifier (Document 10) is absent because promotions
are out of scope for this slice. Only day-of-week seasonality is
exercised; annual/holiday cyclicality is omitted, since a 60-day
window can't meaningfully demonstrate an annual cycle.

Price is not a separate multiplier here (Document 6: baked into
potential demand once, via the product popularity factor -- never a
second, separate actual-demand multiplier). Since price isn't varied
across SKUs in this slice, it is absorbed into the product-popularity
draw rather than modeled as its own term -- a known limitation while
price has nothing to vary against, not a business decision.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np

from simulator.world.config import DemandConfig
from simulator.world.entities import Store


def draw_potential_demand(
    demand_config: DemandConfig, store: Store, rng: np.random.Generator
) -> float:
    """Document 6: store-level baseline x product-level popularity factor.

    Drawn once per (store, SKU) pair, before the day loop -- a
    structural, relatively stable quantity (Document 6's two-stage
    split). Must happen before any day-loop RNG usage, in a fixed pair
    order, so it can never depend on the simulation horizon length
    (see clock.py's truncation-invariance discipline).
    """
    low, high = demand_config.store_baseline_range_by_tier[store.store_scale_class]
    store_baseline = rng.uniform(low, high)
    pop_low, pop_high = demand_config.product_popularity_range
    product_popularity_factor = rng.uniform(pop_low, pop_high)
    return store_baseline * product_popularity_factor


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
    rng: np.random.Generator,
) -> int:
    """Document 6: actual demand = potential demand x seasonal modifier
    x regional shock x idiosyncratic noise, combined in log-space.

    Exactly one scalar RNG draw (the idiosyncratic component) per
    call, so that truncating the simulation horizon can never change
    an earlier day's draw.
    """
    seasonal_modifier = demand_config.weekday_seasonal_modifiers[day.weekday()]
    idiosyncratic_noise = rng.normal(0.0, demand_config.idiosyncratic_noise_sigma)
    log_demand = (
        math.log(potential_demand)
        + math.log(seasonal_modifier)
        + regional_shock
        + idiosyncratic_noise
    )
    return max(0, round(math.exp(log_demand)))
