"""Generate the NovaFoods Store Master / Product Master reference-data
artifacts from the existing Phase 1 snapshot.

Usage: py -3 scripts/run_reference_masters.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator.reference.runner import run_reference_masters  # noqa: E402
from simulator.world.config import DEFAULT_SIMULATION_CONFIG  # noqa: E402
from simulator.world.snapshot import PROVISIONAL_OUTPUT_ROOT  # noqa: E402

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "simulator" / "reference" / "output" / "master"


def main() -> None:
    snapshot_dir = PROVISIONAL_OUTPUT_ROOT / "seed42"
    reference_date = DEFAULT_SIMULATION_CONFIG.run.start_date
    results = run_reference_masters(snapshot_dir, OUTPUT_ROOT, reference_date)
    for name, path in results.items():
        print(f"Wrote {name} to {path}")


if __name__ == "__main__":
    main()
