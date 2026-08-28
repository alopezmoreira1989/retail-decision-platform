"""Document 8 -- physical_inventory state transition.

    closing_inventory[t] = opening_inventory[t] - sales[t] + deliveries[t]
    opening_inventory[t+1] = closing_inventory[t]

deliveries[t] is an external input owned by Document 9 (orders.py);
this module only defines how inventory responds to it.
"""

from __future__ import annotations


def step_inventory(opening_inventory: int, sales: int, deliveries: int) -> int:
    closing_inventory = opening_inventory - sales + deliveries
    # Document 8: "Inventory can never go negative, and this isn't a
    # new rule -- it falls out of Document 7's own definition... nobody
    # should add a defensive floor/clamp later that isn't actually
    # needed." An assertion verifies the invariant instead of a clamp,
    # so a violation surfaces as a bug rather than being silently
    # masked.
    assert closing_inventory >= 0, (
        "physical_inventory went negative -- sales must never exceed "
        "opening inventory; this should be impossible by construction "
        "via sales.compute_sales's min()"
    )
    return closing_inventory
