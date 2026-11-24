"""Tests de prévisualisation CSV et Parquet."""

import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from api.table_preview import (
    MAX_CELL_CHARACTERS,
    preview_csv,
    preview_parquet,
    preview_table,
)


def create_parquet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({
        "feature_id": list(range(250)),
        "mz": [100.0 + index / 10 for index in range(250)],
        "sample": [f"sample_{index % 5}" for index in range(250)],
    })
    pq.write_table(table, path, row_group_size=40)


def create_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["feature_id", "description"],
        )
        writer.writeheader()
        for index in range(120):
            writer.writerow({
                "feature_id": index,
                "description": "x" * 700 if index == 55 else f"feature_{index}",
            })


def test_parquet_preview_reads_requested_page(tmp_path: Path) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)
    preview = preview_parquet(
        path, offset=85, limit=25, columns=["feature_id", "mz"]
    )
    assert preview["total"] == 250
    assert preview["returned"] == 25
    assert preview["has_more"] is True
    assert preview["rows"][0]["feature_id"] == 85
    assert preview["rows"][-1]["feature_id"] == 109


def test_parquet_preview_handles_last_page(tmp_path: Path) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)
    preview = preview_parquet(path, offset=240, limit=50)
    assert preview["returned"] == 10
    assert preview["has_more"] is False


def test_csv_preview_streams_and_truncates_cells(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    create_csv(path)
    preview = preview_csv(path, offset=50, limit=10)
    assert preview["total"] == 120
    assert preview["rows"][0]["feature_id"] == "50"
    value = preview["rows"][5]["description"]
    assert len(value) == MAX_CELL_CHARACTERS + 1
    assert value.endswith("…")


def test_preview_rejects_invalid_pagination(tmp_path: Path) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)
    with pytest.raises(ValueError, match="comprise entre 1 et 100"):
        preview_parquet(path, offset=0, limit=101)


def test_preview_rejects_unknown_columns(tmp_path: Path) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)
    with pytest.raises(ValueError, match="Colonnes inconnues"):
        preview_parquet(path, offset=0, limit=10, columns=["unknown"])


def test_preview_resolves_table_from_manifest(tmp_path: Path) -> None:
    path = (
        tmp_path / "data" / "output" / "feature_matrix"
        / "features_complete.parquet"
    )
    create_parquet(path)
    preview = preview_table(
        "job-table", tmp_path, "identified-features", offset=10, limit=5
    )
    assert preview["result_id"] == "identified-features"
    assert preview["returned"] == 5
    assert preview["rows"][0]["feature_id"] == 10
