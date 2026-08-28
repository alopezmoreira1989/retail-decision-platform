"""Top-level NovaFoods reference-data orchestration: read a Phase 1
snapshot (read-only) and generate the Store Master / Product Master
artifacts as of a single reference date.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from simulator.reference import writer as writer_mod
from simulator.reference.product_master import generate_product_master
from simulator.reference.snapshot_reader import read_phase1_reference_snapshot
from simulator.reference.store_master import generate_store_master


def run_reference_masters(
    snapshot_dir: Path, output_dir: Path, reference_date: date
) -> dict[str, Path]:
    snapshot = read_phase1_reference_snapshot(snapshot_dir)
    store_master_rows = generate_store_master(snapshot.stores, reference_date)
    product_master_rows = generate_product_master(snapshot.skus, snapshot.products, reference_date)

    return {
        "store_master": writer_mod.write_store_master(output_dir, store_master_rows),
        "product_master": writer_mod.write_product_master(output_dir, product_master_rows),
    }
