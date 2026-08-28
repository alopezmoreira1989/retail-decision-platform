"""NovaFoods Product Master -- authoritative NovaFoods reference data,
Document 2's Category/Subcategory/Brand/Product/SKU hierarchy. NOT a
retailer feed -- see store_master.py's module docstring for the same
reasoning. Deliberately carries no price field: Document 2 keeps price
a separate, time-versioned concept, and no price is implemented
anywhere in this slice's Ground Truth (see the POS source-contract
stop-condition report) -- there is nothing to expose here even if we
wanted to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from simulator.reference.snapshot_reader import ProductReferenceFact, SkuReferenceFact


def _sku_lifecycle_state(fact: SkuReferenceFact, reference_date: date) -> str:
    """Same semantics and precedence as
    `simulator.world.entities.sku_lifecycle_state` -- re-derived here,
    not imported, for the same reason store_master.py re-derives its
    own lifecycle function.
    """
    if fact.discontinued_on is not None and reference_date >= fact.discontinued_on:
        return "DISCONTINUED"
    if (
        fact.temp_unavailable_effective_from is not None
        and fact.temp_unavailable_effective_to is not None
        and fact.temp_unavailable_effective_from
        <= reference_date
        <= fact.temp_unavailable_effective_to
    ):
        return "TEMPORARILY_UNAVAILABLE"
    return "ACTIVE"


@dataclass(frozen=True)
class ProductMasterRow:
    sku_id: str
    product_id: str
    product_name: str
    category: str
    subcategory: str
    brand: str
    pack_size: str
    country: str
    units_per_case: int
    lifecycle_state: str


def generate_product_master(
    skus: tuple[SkuReferenceFact, ...],
    products: tuple[ProductReferenceFact, ...],
    reference_date: date,
) -> list[ProductMasterRow]:
    products_by_id = {product.product_id: product for product in products}
    rows: list[ProductMasterRow] = []
    for sku in skus:
        product = products_by_id[sku.product_id]
        rows.append(
            ProductMasterRow(
                sku_id=sku.sku_id,
                product_id=product.product_id,
                product_name=product.product_name,
                category=product.category,
                subcategory=product.subcategory,
                brand=product.brand,
                pack_size=sku.pack_size,
                country=sku.country,
                units_per_case=sku.units_per_case,
                lifecycle_state=_sku_lifecycle_state(sku, reference_date),
            )
        )
    return rows
