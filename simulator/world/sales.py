"""Document 7 -- Actual Sales = min(Actual Demand, opening inventory).

Sales needs no Latent/Observable/Inference split (Document 7's
conclusion) and depends only on same-day demand and the inventory
carried forward from the previous day -- never on anything later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SalesResult:
    sales: int
    unmet_demand: int
    stockout: bool
    # Document 8 (corrected): a stockout event is any day with positive
    # unmet demand, regardless of whether opening inventory was
    # exactly zero or merely insufficient to cover that day's demand.
    # Ground-truth-only -- never exposed outside Phase 1 / the
    # evaluation harness (see snapshot.py).


def compute_sales(actual_demand: int, opening_inventory: int) -> SalesResult:
    sales = min(actual_demand, opening_inventory)
    unmet_demand = actual_demand - sales
    stockout = unmet_demand > 0
    return SalesResult(sales=sales, unmet_demand=unmet_demand, stockout=stockout)
