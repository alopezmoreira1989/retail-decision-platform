"""Writes Phase 2 source artifacts to a deterministic landing
directory tree (Vertical Slice #1 design brief, Section 11):

    landing/{profile_name}/{retailer_id}/{feed}/{delivery_period}/...

The `{retailer_id}` path segment is NovaFoods' own internal reference,
used purely for landing organization -- it is not a claim about what
identifiers appear inside the artifact content, which always use the
profile's retailer-local mapping. The delivery mechanism (see
profiles.py's `FEED_DELIVERY_MECHANISM` -- "cloud_object_landing" for
POS, "document_repository" for Assortment) is simulated conceptually
only: this directory tree stands in for what the eventual GCS bucket
or Nextcloud folder would hold, never an operated service. A missing
delivery is represented by the complete absence of a delivery-period
directory -- nothing is created for it at all, so "no artifact" is
directly observable on disk, not just a flag inside one.

`manifest.json` represents the simulated DELIVERY/LANDING event
(Source & Delivery Model checkpoint, Section 4/11) -- NovaFoods-side
metadata about receiving the artifact (`delivered_on`, duplicate/
missing characteristics). It is never casing-adjusted per profile,
because it is not retailer-authored content -- it is Phase 2's own
representation of the landing system, which has no notion of "Profile
A's naming convention." Column casing (Section 7: the only approved
schema difference between Profile A and B) applies exclusively to the
artifact's own header row, derived here from each row dataclass's
field order via `POS_COLUMN_ORDER`/`ASSORTMENT_COLUMN_ORDER` so the
column set and its order can never drift from what pos.py/assortment.py
actually generate.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from simulator.feeds.assortment import ASSORTMENT_COLUMN_ORDER, AssortmentArtifact
from simulator.feeds.pos import POS_COLUMN_ORDER, PosArtifact
from simulator.feeds.profiles import COLUMN_CASING_UPPER_SNAKE_CASE

_FIXED_XLSX_TIMESTAMP = datetime(2000, 1, 1)
_FIXED_ZIP_DATE_TIME = (2000, 1, 1, 0, 0, 0)


def _header_for(column_order: tuple[str, ...], column_casing: str) -> list[str]:
    if column_casing == COLUMN_CASING_UPPER_SNAKE_CASE:
        return [name.upper() for name in column_order]
    return list(column_order)


def _cell_value(value: object) -> object:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _write_manifest(period_dir: Path, manifest: dict) -> None:
    (period_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def _write_pos_csv(path: Path, artifact: PosArtifact, column_casing: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(_header_for(POS_COLUMN_ORDER, column_casing))
        for row in artifact.rows:
            writer.writerow([_cell_value(getattr(row, name)) for name in POS_COLUMN_ORDER])


def write_pos_artifacts(
    landing_root: Path, feed_format: str, column_casing: str, artifacts: list[PosArtifact]
) -> None:
    if feed_format != "csv":
        raise ValueError(
            f"Vertical Slice #1 only implements POS format 'csv', got {feed_format!r}."
        )

    by_period: dict[date, list[PosArtifact]] = defaultdict(list)
    for artifact in artifacts:
        by_period[artifact.delivery_period].append(artifact)

    for period, period_artifacts in sorted(by_period.items()):
        period_dir = landing_root / "POS" / period.isoformat()
        period_dir.mkdir(parents=True, exist_ok=True)

        filenames = []
        for artifact in period_artifacts:
            filename = "pos.duplicate.csv" if artifact.is_duplicate else "pos.csv"
            _write_pos_csv(period_dir / filename, artifact, column_casing)
            filenames.append(filename)

        primary = period_artifacts[0]
        _write_manifest(
            period_dir,
            {
                "feed": "POS",
                "delivery_period": period.isoformat(),
                "delivered_on": primary.delivered_on.isoformat(),
                "row_count": len(primary.rows),
                "files": sorted(filenames),
                "duplicate_delivery": len(period_artifacts) > 1,
            },
        )


def _write_assortment_csv(path: Path, artifact: AssortmentArtifact, column_casing: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(_header_for(ASSORTMENT_COLUMN_ORDER, column_casing))
        for row in artifact.rows:
            writer.writerow([_cell_value(getattr(row, name)) for name in ASSORTMENT_COLUMN_ORDER])


_CORE_PROPS_MODIFIED_RE = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")
_FIXED_CORE_PROPS_MODIFIED = rb"\g<1>2000-01-01T00:00:00Z\g<2>"


def _normalize_zip_timestamps(path: Path) -> None:
    """openpyxl's .xlsx output embeds two independent sources of
    nondeterminism, discovered empirically while verifying the
    reproducibility invariant (Section 12) actually holds for XLSX:

    1. Each zip entry's own write timestamp, which varies run-to-run
       even when content is otherwise identical -- normalized below by
       rewriting every entry with a fixed `date_time`.
    2. `docProps/core.xml`'s `<dcterms:modified>` field, which openpyxl
       stamps with `datetime.now()` at save time regardless of the
       `workbook.properties.modified` override set in
       `_write_assortment_xlsx` -- that override is silently
       superseded by openpyxl's own writer, so it has to be corrected
       here, after the fact, on the actual XML text.

    Without both fixes, "same profile + seed -> identical bytes" would
    hold for every artifact except Assortment XLSX, intermittently --
    exactly the kind of gap this invariant exists to catch.
    """
    original_bytes = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(original_bytes)) as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]

    normalized = io.BytesIO()
    with zipfile.ZipFile(normalized, "w", zipfile.ZIP_DEFLATED) as target:
        for info, data in entries:
            if info.filename == "docProps/core.xml":
                data = _CORE_PROPS_MODIFIED_RE.sub(_FIXED_CORE_PROPS_MODIFIED, data)
            new_info = zipfile.ZipInfo(info.filename, date_time=_FIXED_ZIP_DATE_TIME)
            new_info.compress_type = zipfile.ZIP_DEFLATED
            new_info.external_attr = info.external_attr
            target.writestr(new_info, data)

    path.write_bytes(normalized.getvalue())


def _write_assortment_xlsx(path: Path, artifact: AssortmentArtifact, column_casing: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "assortment"
    sheet.append(_header_for(ASSORTMENT_COLUMN_ORDER, column_casing))
    for row in artifact.rows:
        sheet.append([_cell_value(getattr(row, name)) for name in ASSORTMENT_COLUMN_ORDER])

    # Strip nondeterministic document metadata (openpyxl defaults
    # created/modified to datetime.now()) -- required for reproducible
    # bytes, same reasoning as _normalize_zip_timestamps below.
    workbook.properties.creator = "phase2-simulator"
    workbook.properties.lastModifiedBy = "phase2-simulator"
    workbook.properties.created = _FIXED_XLSX_TIMESTAMP
    workbook.properties.modified = _FIXED_XLSX_TIMESTAMP

    workbook.save(path)
    _normalize_zip_timestamps(path)


def write_assortment_artifacts(
    landing_root: Path, feed_format: str, column_casing: str, artifacts: list[AssortmentArtifact]
) -> None:
    for artifact in artifacts:
        period_dir = landing_root / "ASSORTMENT" / artifact.delivery_period.isoformat()
        period_dir.mkdir(parents=True, exist_ok=True)

        if feed_format == "csv":
            filename = "assortment.csv"
            _write_assortment_csv(period_dir / filename, artifact, column_casing)
        elif feed_format == "xlsx":
            filename = "assortment.xlsx"
            _write_assortment_xlsx(period_dir / filename, artifact, column_casing)
        else:
            raise ValueError(
                "Vertical Slice #1 only implements Assortment formats 'csv'/'xlsx', "
                f"got {feed_format!r}."
            )

        _write_manifest(
            period_dir,
            {
                "feed": "ASSORTMENT",
                "delivery_period": artifact.delivery_period.isoformat(),
                "delivered_on": artifact.delivered_on.isoformat(),
                "source_as_of_date": artifact.source_as_of_date.isoformat(),
                "row_count": len(artifact.rows),
                "file": filename,
            },
        )
