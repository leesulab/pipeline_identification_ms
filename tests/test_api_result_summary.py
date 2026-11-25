"""Tests HTTP de la synthèse scientifique."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from api.app import app
from api.jobs import create_job


client = TestClient(app)


def create_summary_job(
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
            "project": "Summary test",
        },
    )

    features_file = (
        Path(job["working_dir"])
        / "data"
        / "output"
        / "feature_matrix"
        / "features_complete.parquet"
    )

    features_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pq.write_table(
        pa.table(
            {
                "feature_idx": [1, 1, 2, 3, 4],
                "match_name": [
                    "Molecule A",
                    "Molecule B",
                    "Molecule C",
                    None,
                    "",
                ],
                "global_score": [
                    0.9,
                    0.8,
                    0.7,
                    None,
                    None,
                ],
                "confidence_level": [
                    1.0,
                    2.0,
                    3.0,
                    None,
                    5.0,
                ],
                "samples": [
                    "sample_a,sample_b",
                    "sample_a,sample_b",
                    "sample_b",
                    "sample_c",
                    "sample_c",
                ],
            }
        ),
        features_file,
    )

    return job


def test_result_summary_endpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    job = create_summary_job(
        tmp_path,
        monkeypatch,
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/results/summary"
    )

    assert response.status_code == 200

    summary = response.json()

    assert summary["row_count"] == 5
    assert summary["unique_feature_count"] == 4
    assert summary["identified_row_count"] == 3
    assert summary["identified_feature_count"] == 2

    assert summary[
        "feature_identification_rate"
    ] == 0.5

    assert summary["distinct_molecule_count"] == 3
    assert summary["median_global_score"] == 0.8
    assert summary["sample_count"] == 3

    assert summary["confidence_distribution"] == [
        {
            "confidence_level": 1,
            "row_count": 1,
            "feature_count": 1,
        },
        {
            "confidence_level": 2,
            "row_count": 1,
            "feature_count": 1,
        },
        {
            "confidence_level": 3,
            "row_count": 1,
            "feature_count": 1,
        },
        {
            "confidence_level": 5,
            "row_count": 1,
            "feature_count": 1,
        },
    ]


def test_result_summary_returns_404_without_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["file_discovery"],
        parameters={},
    )

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}"
        "/results/summary"
    )

    assert response.status_code == 404

    assert "features complètes introuvable" in (
        response.json()["detail"]
    )


def test_result_summary_route_is_in_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert (
        "/api/v1/jobs/{job_id}/results/summary"
        in paths
    )
