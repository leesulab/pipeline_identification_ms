"""Tests HTTP du manifeste des résultats."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from api.jobs import create_job


client = TestClient(app)


def test_result_manifest_endpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )

    job = create_job(
        steps=["file_discovery"],
        parameters={
            "project": "Manifest test",
        },
    )

    output_dir = (
        Path(job["working_dir"])
        / "data"
        / "output"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    image = output_dir / "molecules_per_sample.png"
    image.write_bytes(b"image")

    response = client.get(
        f"/api/v1/jobs/{job['job_id']}/results"
    )

    assert response.status_code == 200

    manifest = response.json()

    assert manifest["version"] == 1
    assert manifest["job_id"] == job["job_id"]
    assert len(manifest["results"]) == 1

    result = manifest["results"][0]

    assert result["id"] == "molecules-per-sample"
    assert result["kind"] == "image"
    assert result["group"] == "visualizations"
    assert result["size_bytes"] == 5
    assert result["relative_path"] == (
        "data/output/molecules_per_sample.png"
    )


def test_result_manifest_returns_404_for_unknown_job() -> None:
    response = client.get(
        "/api/v1/jobs/unknown-job/results"
    )

    assert response.status_code == 404


def test_result_manifest_route_is_in_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert (
        "/api/v1/jobs/{job_id}/results"
        in paths
    )
