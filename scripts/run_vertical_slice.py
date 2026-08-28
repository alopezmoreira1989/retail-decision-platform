"""Run Vertical Slice #1.5 and persist its output as Parquet.

Usage: py -3 scripts/run_vertical_slice.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator.world.clock import run_slice  # noqa: E402
from simulator.world.config import DEFAULT_SIMULATION_CONFIG  # noqa: E402
from simulator.world.snapshot import write_snapshot  # noqa: E402


def main() -> None:
    result = run_slice(DEFAULT_SIMULATION_CONFIG)
    out_dir = write_snapshot(result)
    print(
        f"Wrote {len(result.days)} daily rows "
        f"({len(result.stores)} stores x {len(result.skus)} SKUs) "
        f"and {len(result.orders)} orders to {out_dir}"
    )


if __name__ == "__main__":
    main()
