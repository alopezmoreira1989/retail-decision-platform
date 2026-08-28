"""Tests for the NovaFoods-owned reference-data layer (Store Master,
Product Master) -- authoritative NovaFoods reference data, not a
retailer feed: no RetailerFeedProfile, no Profile A/B, no faults.

All tests read the real, already-generated Phase 1 snapshot at
SNAPSHOT_DIR read-only; none of them regenerate or mutate it.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import fields
from datetime import date, timedelta
from pathlib import Path

import pytest

from simulator.reference.product_master import ProductMasterRow, generate_product_master
from simulator.reference.runner import run_reference_masters
from simulator.reference.snapshot_reader import (
    _STORE_COLUMNS,
    read_phase1_reference_snapshot,
)
from simulator.reference.store_master import StoreMasterRow, generate_store_master
from simulator.reference.writer import (
    PRODUCT_MASTER_COLUMN_ORDER,
    STORE_MASTER_COLUMN_ORDER,
)

SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[3] / "simulator" / "world" / "output" / "dev_slice" / "seed42"
)
REFERENCE_DATE = date(2026, 1, 1)  # matches Phase 1's run_start_date


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def snapshot():
    return read_phase1_reference_snapshot(SNAPSHOT_DIR)


# ---------------------------------------------------------------------
# store_scale_class exclusion -- the hard constraint
# ---------------------------------------------------------------------


def test_store_scale_class_is_never_requested_from_disk():
    """Structural guarantee: the reference layer's own column allow-
    list never asks for store_scale_class, so it cannot leak even by
    accident."""
    assert "store_scale_class" not in _STORE_COLUMNS


def test_store_scale_class_absent_from_store_master_schema():
    assert "store_scale_class" not in STORE_MASTER_COLUMN_ORDER
    assert "store_scale_class" not in {f.name for f in fields(StoreMasterRow)}


def test_store_scale_class_absent_from_generated_rows(snapshot):
    rows = generate_store_master(snapshot.stores, REFERENCE_DATE)
    for row in rows:
        assert not hasattr(row, "store_scale_class")


# ---------------------------------------------------------------------
# Store Master
# ---------------------------------------------------------------------


def test_store_master_contains_the_approved_fields_in_the_approved_order():
    assert STORE_MASTER_COLUMN_ORDER == (
        "store_id",
        "retailer_id",
        "format",
        "region",
        "address",
        "city",
        "state_province",
        "lat",
        "long",
        "open_date",
        "lifecycle_state",
    )


def test_store_master_ids_are_canonical_not_retailer_local(snapshot):
    rows = generate_store_master(snapshot.stores, REFERENCE_DATE)
    for row in rows:
        assert row.store_id.startswith("STORE-")
        assert not row.store_id.startswith("STORE-A")  # not a Phase 2 retailer-local code
        assert row.retailer_id == "RETAILER-001"


def test_store_master_geography_is_coherent(snapshot):
    rows = generate_store_master(snapshot.stores, REFERENCE_DATE)
    assert len(rows) == 6
    for row in rows:
        assert row.address
        assert row.city
        assert row.state_province
        assert isinstance(row.lat, float)
        assert isinstance(row.long, float)


def test_store_master_open_date_is_coherent(snapshot):
    rows = generate_store_master(snapshot.stores, REFERENCE_DATE)
    for row in rows:
        assert row.open_date <= REFERENCE_DATE


def test_store_master_lifecycle_states_are_valid_and_reflect_the_real_closure(snapshot):
    valid_states = {"OPEN", "TEMPORARILY_CLOSED", "CLOSED"}
    rows_at_start = generate_store_master(snapshot.stores, REFERENCE_DATE)
    for row in rows_at_start:
        assert row.lifecycle_state in valid_states
        assert row.lifecycle_state == "OPEN"  # nothing closed yet at day 0

    # STORE-006's real closure window is days 15-22 (see config.py)
    during_closure = generate_store_master(snapshot.stores, REFERENCE_DATE + timedelta(days=18))
    store_006 = next(r for r in during_closure if r.store_id == "STORE-006")
    assert store_006.lifecycle_state == "TEMPORARILY_CLOSED"
    others = [r for r in during_closure if r.store_id != "STORE-006"]
    assert all(r.lifecycle_state == "OPEN" for r in others)

    after_closure = generate_store_master(snapshot.stores, REFERENCE_DATE + timedelta(days=25))
    store_006_after = next(r for r in after_closure if r.store_id == "STORE-006")
    assert store_006_after.lifecycle_state == "OPEN"  # reopened, non-terminal


def test_store_master_closed_state_is_reachable_and_coherent():
    """No store in the real 60-day world is permanently CLOSED (a
    deliberate choice -- see config.py), so this is exercised directly
    against the generator with a synthetic fact, mirroring the
    corresponding isolated unit test in
    tests/simulator/world/test_vertical_slice.py.
    """
    from simulator.reference.snapshot_reader import StoreReferenceFact

    closed_fact = StoreReferenceFact(
        store_id="STORE-999",
        retailer_id="RETAILER-001",
        format="Supermarket",
        region="North",
        address="1 Test St",
        city="Testville",
        state_province="TS",
        lat=0.0,
        long=0.0,
        open_date=date(2020, 1, 1),
        closure_effective_from=None,
        closure_effective_to=None,
        closed_date=date(2026, 2, 1),
    )
    before = generate_store_master((closed_fact,), date(2026, 1, 31))
    on_and_after = generate_store_master((closed_fact,), date(2026, 2, 1))
    well_after = generate_store_master((closed_fact,), date(2026, 12, 1))
    assert before[0].lifecycle_state == "OPEN"
    assert on_and_after[0].lifecycle_state == "CLOSED"
    assert well_after[0].lifecycle_state == "CLOSED"  # terminal, no return


# ---------------------------------------------------------------------
# Product Master
# ---------------------------------------------------------------------


def test_product_master_contains_the_approved_fields_in_the_approved_order():
    assert PRODUCT_MASTER_COLUMN_ORDER == (
        "sku_id",
        "product_id",
        "product_name",
        "category",
        "subcategory",
        "brand",
        "pack_size",
        "country",
        "units_per_case",
        "lifecycle_state",
    )


def test_no_price_field_in_product_master_schema():
    price_like_names = {"price", "list_price", "unit_price", "wholesale_price"}
    assert price_like_names.isdisjoint(PRODUCT_MASTER_COLUMN_ORDER)
    assert price_like_names.isdisjoint({f.name for f in fields(ProductMasterRow)})


def test_product_master_ids_are_canonical_not_retailer_local(snapshot):
    rows = generate_product_master(snapshot.skus, snapshot.products, REFERENCE_DATE)
    for row in rows:
        assert row.sku_id.startswith("SKU-")
        assert not row.sku_id.startswith("ITEM-")  # not a Phase 2 retailer-local code


def test_product_sku_relationship_is_correctly_joined(snapshot):
    rows = generate_product_master(snapshot.skus, snapshot.products, REFERENCE_DATE)
    products_by_id = {p.product_id: p for p in snapshot.products}
    for row in rows:
        product = products_by_id[row.product_id]
        assert row.product_name == product.product_name
        assert row.category == product.category
        assert row.subcategory == product.subcategory
        assert row.brand == product.brand


def test_category_subcategory_and_brand_hierarchy_present(snapshot):
    rows = generate_product_master(snapshot.skus, snapshot.products, REFERENCE_DATE)
    assert len({r.category for r in rows}) > 1
    assert len({r.subcategory for r in rows}) > 1
    assert len({r.brand for r in rows}) > 1


def test_country_and_pack_size_present(snapshot):
    rows = generate_product_master(snapshot.skus, snapshot.products, REFERENCE_DATE)
    for row in rows:
        assert row.country == "US"
        assert row.pack_size


def test_product_master_lifecycle_reflects_the_real_discontinuation(snapshot):
    rows_at_start = generate_product_master(snapshot.skus, snapshot.products, REFERENCE_DATE)
    sku_003_at_start = next(r for r in rows_at_start if r.sku_id == "SKU-003")
    assert sku_003_at_start.lifecycle_state == "ACTIVE"

    # SKU-003's real discontinued_on is day 54 (see config.py)
    rows_after = generate_product_master(
        snapshot.skus, snapshot.products, REFERENCE_DATE + timedelta(days=54)
    )
    sku_003_after = next(r for r in rows_after if r.sku_id == "SKU-003")
    assert sku_003_after.lifecycle_state == "DISCONTINUED"

    others = [r for r in rows_after if r.sku_id != "SKU-003"]
    assert all(r.lifecycle_state == "ACTIVE" for r in others)


def test_product_master_temporarily_unavailable_is_reachable_and_coherent(snapshot):
    """No SKU in the real 60-day world enters TEMPORARILY_UNAVAILABLE
    (see config.py), so this is exercised directly against the
    generator with a synthetic fact.
    """
    from simulator.reference.snapshot_reader import ProductReferenceFact, SkuReferenceFact

    unavailable_fact = SkuReferenceFact(
        sku_id="SKU-999",
        product_id="PRODUCT-999",
        units_per_case=12,
        pack_size="1 unit",
        country="US",
        discontinued_on=None,
        temp_unavailable_effective_from=date(2026, 1, 10),
        temp_unavailable_effective_to=date(2026, 1, 20),
    )
    product_fact = ProductReferenceFact(
        product_id="PRODUCT-999",
        product_name="Test Product",
        category="Test Category",
        subcategory="Test Subcategory",
        brand="Test Brand",
    )
    before = generate_product_master((unavailable_fact,), (product_fact,), date(2026, 1, 9))
    during = generate_product_master((unavailable_fact,), (product_fact,), date(2026, 1, 15))
    after = generate_product_master((unavailable_fact,), (product_fact,), date(2026, 1, 21))
    assert before[0].lifecycle_state == "ACTIVE"
    assert during[0].lifecycle_state == "TEMPORARILY_UNAVAILABLE"
    assert after[0].lifecycle_state == "ACTIVE"  # resumed, non-terminal


# ---------------------------------------------------------------------
# Source ownership: not a retailer feed
# ---------------------------------------------------------------------


def test_reference_masters_are_not_retailer_feeds():
    """No RetailerFeedProfile/Profile-A-B/fault concepts exist anywhere
    in this package -- confirmed structurally by their absence from the
    module namespace, not just by convention.
    """
    import simulator.reference.product_master as product_master_mod
    import simulator.reference.store_master as store_master_mod

    for module in (product_master_mod, store_master_mod):
        assert not hasattr(module, "RetailerFeedProfile")
        assert not hasattr(module, "PosFaultProfile")
        assert not hasattr(module, "AssortmentFaultProfile")


# ---------------------------------------------------------------------
# Determinism and Phase 1 integrity
# ---------------------------------------------------------------------


def test_reference_masters_are_deterministic(tmp_path):
    root_1 = tmp_path / "run1"
    root_2 = tmp_path / "run2"
    run_reference_masters(SNAPSHOT_DIR, root_1, REFERENCE_DATE)
    run_reference_masters(SNAPSHOT_DIR, root_2, REFERENCE_DATE)
    assert _hash_tree(root_1) == _hash_tree(root_2)
    assert len(_hash_tree(root_1)) == 2  # store_master.csv + product_master.csv


def test_phase1_snapshot_unchanged_after_generating_masters(tmp_path):
    before = _hash_tree(SNAPSHOT_DIR)
    run_reference_masters(SNAPSHOT_DIR, tmp_path, REFERENCE_DATE)
    after = _hash_tree(SNAPSHOT_DIR)
    assert before == after


def test_written_store_master_csv_round_trips(tmp_path):
    results = run_reference_masters(SNAPSHOT_DIR, tmp_path, REFERENCE_DATE)
    with results["store_master"].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert list(rows[0].keys()) == list(STORE_MASTER_COLUMN_ORDER)
    assert "store_scale_class" not in rows[0]


def test_written_product_master_csv_round_trips(tmp_path):
    results = run_reference_masters(SNAPSHOT_DIR, tmp_path, REFERENCE_DATE)
    with results["product_master"].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert list(rows[0].keys()) == list(PRODUCT_MASTER_COLUMN_ORDER)
