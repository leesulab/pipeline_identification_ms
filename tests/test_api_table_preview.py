"""Tests HTTP de prévisualisation tabulaire."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from api.app import app
from api.jobs import create_job


client = TestClient(app)


def create_table_job(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["file_discovery"],
        parameters={"project": "Table preview"},
    )

    parquet_path = (
        Path(job["working_dir"])
        / "data"
        / "output"
        / "feature_matrix"
        / "features_complete.parquet"
    )

    parquet_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pq.write_table(
        pa.table(
            {
                "feature_id": list(range(120)),
                "mz": [
                    100.0 + index / 10
                    for index in range(120)
                ],
                "sample": [
                    f"sample_{index % 4}"
                    for index in range(120)
                ],
            }
        ),
        parquet_path,
        row_group_size=25,
    )

    return job


def test_table_preview_endpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_table_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/preview",
        params={
            "offset": 40,
            "limit": 10,
            "columns": "feature_id,mz",
        },
    )

    assert response.status_code == 200

    preview = response.json()

    assert preview["result_id"] == (
        "identified-features"
    )
    assert preview["format"] == "parquet"
    assert preview["total"] == 120
    assert preview["returned"] == 10
    assert preview["has_more"] is True

    assert preview["rows"][0]["feature_id"] == 40
    assert preview["rows"][-1]["feature_id"] == 49

    assert [
        column["name"]
        for column in preview["columns"]
    ] == ["feature_id", "mz"]


def test_table_preview_rejects_excessive_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_table_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/preview",
        params={
            "limit": 101,
        },
    )

    assert response.status_code == 422


def test_table_preview_rejects_unknown_column(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_table_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/preview",
        params={
            "columns": "unknown",
        },
    )

    assert response.status_code == 422
    assert "Colonnes inconnues" in (
        response.json()["detail"]
    )


def test_table_preview_route_is_in_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert (
        "/api/v1/jobs/{job_id}/tables/"
        "{result_id}/preview"
        in paths
    )


def test_table_preview_sorts_globally(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_table_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/preview",
        params={
            "offset": 0,
            "limit": 5,
            "columns": "feature_id,mz",
            "sort_by": "mz",
            "sort_direction": "desc",
        },
    )

    assert response.status_code == 200

    preview = response.json()

    assert preview["sort_by"] == "mz"
    assert preview["sort_direction"] == "desc"

    assert [
        row["feature_id"]
        for row in preview["rows"]
    ] == [119, 118, 117, 116, 115]


def test_table_preview_sort_is_kept_on_next_page(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_table_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/preview",
        params={
            "offset": 5,
            "limit": 5,
            "columns": "feature_id",
            "sort_by": "feature_id",
            "sort_direction": "asc",
        },
    )

    assert response.status_code == 200

    assert [
        row["feature_id"]
        for row in response.json()["rows"]
    ] == [5, 6, 7, 8, 9]


def test_table_preview_rejects_invalid_sort(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_table_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/tables/identified-features/preview",
        params={
            "sort_by": "global_score",
            "sort_direction": "sideways",
        },
    )

    assert response.status_code == 422
