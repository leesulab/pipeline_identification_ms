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


def test_parquet_preview_sorts_globally_descending(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    preview = preview_parquet(
        path,
        offset=0,
        limit=5,
        columns=["feature_id", "mz"],
        sort_by="mz",
        sort_direction="desc",
    )

    assert [
        row["feature_id"]
        for row in preview["rows"]
    ] == [249, 248, 247, 246, 245]

    assert preview["sort_by"] == "mz"
    assert preview["sort_direction"] == "desc"


def test_parquet_preview_sort_is_preserved_across_pages(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    first_page = preview_parquet(
        path,
        offset=0,
        limit=5,
        columns=["feature_id"],
        sort_by="feature_id",
        sort_direction="asc",
    )

    second_page = preview_parquet(
        path,
        offset=5,
        limit=5,
        columns=["feature_id"],
        sort_by="feature_id",
        sort_direction="asc",
    )

    assert [
        row["feature_id"]
        for row in first_page["rows"]
    ] == [0, 1, 2, 3, 4]

    assert [
        row["feature_id"]
        for row in second_page["rows"]
    ] == [5, 6, 7, 8, 9]


def test_parquet_preview_rejects_unknown_sort_column(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    with pytest.raises(
        ValueError,
        match="Colonne de tri inconnue",
    ):
        preview_parquet(
            path,
            offset=0,
            limit=10,
            sort_by="unknown",
            sort_direction="asc",
        )


def test_parquet_preview_rejects_invalid_sort_direction(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    with pytest.raises(
        ValueError,
        match="direction de tri",
    ):
        preview_parquet(
            path,
            offset=0,
            limit=10,
            sort_by="mz",
            sort_direction="sideways",
        )


def test_parquet_preview_combines_numeric_filters(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    preview = preview_parquet(
        path,
        offset=0,
        limit=50,
        columns=["feature_id", "mz"],
        sort_by="feature_id",
        sort_direction="asc",
        filters=[
            {
                "column": "feature_id",
                "operator": "gte",
                "value": 100,
            },
            {
                "column": "feature_id",
                "operator": "lt",
                "value": 110,
            },
        ],
    )

    assert preview["total"] == 10
    assert preview["returned"] == 10

    assert [
        row["feature_id"]
        for row in preview["rows"]
    ] == list(range(100, 110))


def test_parquet_preview_filters_text_case_insensitively(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    preview = preview_parquet(
        path,
        offset=0,
        limit=20,
        columns=["feature_id", "sample"],
        filters=[
            {
                "column": "sample",
                "operator": "contains",
                "value": "SAMPLE_2",
            },
        ],
    )

    assert preview["total"] == 50

    assert all(
        row["sample"] == "sample_2"
        for row in preview["rows"]
    )


def test_parquet_preview_filters_null_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nullable.parquet"

    pq.write_table(
        pa.table(
            {
                "id": [1, 2, 3, 4],
                "score": [
                    0.5,
                    None,
                    0.8,
                    None,
                ],
            }
        ),
        path,
    )

    preview = preview_parquet(
        path,
        offset=0,
        limit=10,
        columns=["id", "score"],
        filters=[
            {
                "column": "score",
                "operator": "is_null",
            },
        ],
    )

    assert preview["total"] == 2

    assert [
        row["id"]
        for row in preview["rows"]
    ] == [2, 4]


def test_parquet_preview_filters_non_null_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nullable.parquet"

    pq.write_table(
        pa.table(
            {
                "id": [1, 2, 3, 4],
                "score": [
                    0.5,
                    None,
                    0.8,
                    None,
                ],
            }
        ),
        path,
    )

    preview = preview_parquet(
        path,
        offset=0,
        limit=10,
        columns=["id", "score"],
        sort_by="score",
        sort_direction="desc",
        filters=[
            {
                "column": "score",
                "operator": "not_null",
            },
        ],
    )

    assert preview["total"] == 2
    assert preview["returned"] == 2

    assert [
        row["id"]
        for row in preview["rows"]
    ] == [3, 1]


def test_parquet_preview_rejects_unknown_filter_column(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    with pytest.raises(
        ValueError,
        match="Colonne de filtre inconnue",
    ):
        preview_parquet(
            path,
            offset=0,
            limit=10,
            filters=[
                {
                    "column": "unknown",
                    "operator": "eq",
                    "value": 1,
                },
            ],
        )


def test_parquet_preview_rejects_unknown_operator(
    tmp_path: Path,
) -> None:
    path = tmp_path / "table.parquet"
    create_parquet(path)

    with pytest.raises(
        ValueError,
        match="Opérateur de filtre inconnu",
    ):
        preview_parquet(
            path,
            offset=0,
            limit=10,
            filters=[
                {
                    "column": "mz",
                    "operator": "approximately",
                    "value": 120,
                },
            ],
        )
