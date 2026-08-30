"""Shared pytest fixtures.

Some tests (simulator/feeds, simulator/reference) read a pre-generated
Phase 1 snapshot from disk instead of running the slice themselves, to
keep those test modules focused on Phase 2 / reference-data behavior
rather than re-deriving Ground Truth on every run. That snapshot lives
under simulator/world/output/, which is gitignored (*.parquet), so it
does not exist on a fresh checkout (e.g. CI). This fixture builds it
once per test session if it is missing, using the same invocation as
scripts/run_vertical_slice.py.
"""

from __future__ import annotations

import pytest

from simulator.world.clock import run_slice
from simulator.world.config import DEFAULT_SIMULATION_CONFIG
from simulator.world.snapshot import PROVISIONAL_OUTPUT_ROOT, write_snapshot


@pytest.fixture(scope="session", autouse=True)
def phase1_dev_slice_snapshot() -> None:
    seed = DEFAULT_SIMULATION_CONFIG.run.seed
    snapshot_dir = PROVISIONAL_OUTPUT_ROOT / f"seed{seed}"
    if not (snapshot_dir / "stores.parquet").exists():
        result = run_slice(DEFAULT_SIMULATION_CONFIG)
        write_snapshot(result)
