"""Tests HTTP de l’export CSV des vues tabulaires."""

import csv
import io
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from api.app import app
from api.jobs import create_job


client = TestClient(app)


def create_export_job(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["feature_alignment"],
        parameters={
            "project": "CSV export test",
        },
    )

    table_path = (
        Path(job["working_dir"])
        / "data"
        / "output"
        / "feature_matrix"
        / "features_complete.parquet"
    )

    table_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pq.write_table(
        pa.table(
            {
                "feature_id": list(range(20)),
                "match_name": [
                    (
                        f"Molecule {index}"
                        if index % 2 == 0
                        else None
                    )
                    for index in range(20)
                ],
                "global_score": [
                    index / 20
                    for index in range(20)
                ],
            }
        ),
        table_path,
        row_group_size=5,
    )

    return job


def test_table_export_respects_active_view(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_export_job(
        tmp_path,
        monkeypatch,
    )

    filters = [
        {
            "column": "global_score",
            "operator": "gte",
            "value": 0.7,
        },
    ]

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/export.csv",
        params={
            "columns": (
                "feature_id,global_score"
            ),
            "sort_by": "global_score",
            "sort_direction": "desc",
            "filters": json.dumps(filters),
            "filename": "scores-eleves.csv",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/csv"
    )
    assert (
        'filename="scores-eleves.csv"'
        in response.headers["content-disposition"]
    )

    rows = list(
        csv.DictReader(
            io.StringIO(response.text)
        )
    )

    assert [
        int(row["feature_id"])
        for row in rows
    ] == [19, 18, 17, 16, 15, 14]

    assert list(rows[0]) == [
        "feature_id",
        "global_score",
    ]


def test_table_export_rejects_invalid_filter_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_export_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/export.csv",
        params={
            "filters": "{invalid",
        },
    )

    assert response.status_code == 422


def test_table_export_route_is_in_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert (
        "/api/v1/jobs/{job_id}/tables/"
        "{result_id}/export.csv"
        in paths
    )
