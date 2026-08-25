"""Run Phase 2 Vertical Slice #1 (POS + Assortment, Profile A/B)
against the existing Phase 1 snapshot.

Usage: py -3 scripts/run_phase2_slice1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator.feeds.runner import run_vertical_slice_1  # noqa: E402
from simulator.world.snapshot import PROVISIONAL_OUTPUT_ROOT  # noqa: E402

LANDING_ROOT = Path(__file__).resolve().parents[1] / "simulator" / "feeds" / "output" / "landing"


def main() -> None:
    snapshot_dir = PROVISIONAL_OUTPUT_ROOT / "seed42"
    results = run_vertical_slice_1(snapshot_dir, LANDING_ROOT)
    for profile_name, path in results.items():
        print(f"Wrote {profile_name} artifacts to {path}")


if __name__ == "__main__":
    main()
