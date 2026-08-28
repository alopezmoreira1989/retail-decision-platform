"""Writes NovaFoods reference-data master artifacts to disk.

Deliberately distinct from simulator/feeds/landing.py's retailer-feed
writer: no delivery-period folders, no manifest.json (there is no
delivery event to describe -- this is NovaFoods' own reference data,
not something being received from anywhere), no profile/casing
variants, no RetailerFeedProfile. One canonical CSV per master.
"""

from __future__ import annotations

import csv
from dataclasses import fields
from datetime import date
from pathlib import Path

from simulator.reference.product_master import ProductMasterRow
from simulator.reference.store_master import StoreMasterRow

STORE_MASTER_COLUMN_ORDER: tuple[str, ...] = tuple(f.name for f in fields(StoreMasterRow))
PRODUCT_MASTER_COLUMN_ORDER: tuple[str, ...] = tuple(f.name for f in fields(ProductMasterRow))


def _cell_value(value: object) -> object:
    return value.isoformat() if isinstance(value, date) else value


def _write_csv(path: Path, column_order: tuple[str, ...], rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(column_order)
        for row in rows:
            writer.writerow([_cell_value(getattr(row, name)) for name in column_order])


def write_store_master(output_dir: Path, rows: list[StoreMasterRow]) -> Path:
    path = output_dir / "store_master.csv"
    _write_csv(path, STORE_MASTER_COLUMN_ORDER, rows)
    return path


def write_product_master(output_dir: Path, rows: list[ProductMasterRow]) -> Path:
    path = output_dir / "product_master.csv"
    _write_csv(path, PRODUCT_MASTER_COLUMN_ORDER, rows)
    return path
