"""Top-level Vertical Slice #1 orchestration: read a Phase 1 snapshot,
build Profile A and Profile B artifacts against it, and write them to
landing. Nothing downstream of landing (ingestion, RAW, Bronze, ...) is
built here -- see simulator/feeds/README-equivalent guidance in
docs/SIMULATION.md and the approved design brief, Section 16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from simulator.feeds import landing as landing_mod
from simulator.feeds.assortment import (
    AssortmentArtifact,
    generate_assortment_artifacts,
    weekly_delivery_periods,
)
from simulator.feeds.pos import PosArtifact, generate_pos_artifacts
from simulator.feeds.profiles import RetailerFeedProfile, build_profile_a, build_profile_b
from simulator.feeds.snapshot_reader import Phase1Snapshot, read_phase1_snapshot

DEFAULT_PHASE2_SEED = 42


@dataclass(frozen=True)
class GeneratedFeeds:
    profile: RetailerFeedProfile
    pos_artifacts: list[PosArtifact]
    assortment_artifacts: list[AssortmentArtifact]


def generate_profile_feeds(
    snapshot: Phase1Snapshot, profile: RetailerFeedProfile
) -> GeneratedFeeds:
    num_days = (snapshot.run_end_date - snapshot.run_start_date).days + 1
    all_dates = [snapshot.run_start_date + timedelta(days=offset) for offset in range(num_days)]

    pos_feed = profile.feeds.get("POS")
    pos_artifacts: list[PosArtifact] = []
    if pos_feed is not None:
        pos_artifacts = generate_pos_artifacts(
            snapshot.pos_facts,
            all_dates,
            profile.identifier_scheme,
            pos_feed.baseline_latency_days,
            pos_feed.fault_profile,
        )

    assortment_feed = profile.feeds.get("ASSORTMENT")
    assortment_artifacts: list[AssortmentArtifact] = []
    if assortment_feed is not None:
        periods = weekly_delivery_periods(snapshot.run_start_date, num_days)
        assortment_artifacts = generate_assortment_artifacts(
            snapshot.assortment_facts,
            periods,
            snapshot.run_start_date,
            profile.identifier_scheme,
            assortment_feed.baseline_latency_days,
            assortment_feed.fault_profile,
        )

    return GeneratedFeeds(
        profile=profile, pos_artifacts=pos_artifacts, assortment_artifacts=assortment_artifacts
    )


def write_generated_feeds(landing_base: Path, profile_name: str, generated: GeneratedFeeds) -> Path:
    landing_root = landing_base / profile_name / generated.profile.retailer_id

    pos_feed = generated.profile.feeds.get("POS")
    if pos_feed is not None:
        landing_mod.write_pos_artifacts(
            landing_root, pos_feed.format, pos_feed.column_casing, generated.pos_artifacts
        )

    assortment_feed = generated.profile.feeds.get("ASSORTMENT")
    if assortment_feed is not None:
        landing_mod.write_assortment_artifacts(
            landing_root,
            assortment_feed.format,
            assortment_feed.column_casing,
            generated.assortment_artifacts,
        )

    return landing_root


def run_vertical_slice_1(
    snapshot_dir: Path, landing_base: Path, phase2_seed: int = DEFAULT_PHASE2_SEED
) -> dict[str, Path]:
    """Reads the Phase 1 snapshot at `snapshot_dir` (read-only) and
    writes both profiles' artifacts under `landing_base`. Returns each
    profile's landing root, keyed by profile name.
    """
    snapshot = read_phase1_snapshot(snapshot_dir)

    profile_a = build_profile_a(snapshot.retailer_id, snapshot.store_ids, snapshot.sku_ids)
    profile_b = build_profile_b(
        snapshot.retailer_id,
        snapshot.store_ids,
        snapshot.sku_ids,
        snapshot.run_start_date,
        phase2_seed,
    )

    results: dict[str, Path] = {}
    for profile_name, profile in (("profile_a", profile_a), ("profile_b", profile_b)):
        generated = generate_profile_feeds(snapshot, profile)
        results[profile_name] = write_generated_feeds(landing_base, profile_name, generated)
    return results
