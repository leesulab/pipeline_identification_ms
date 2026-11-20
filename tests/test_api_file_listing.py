"""Tests de l'inventaire des fichiers d'un job."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_list_job_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )

    create_response = client.post(
        "/api/v1/jobs",
        json={"steps": ["file_discovery"]},
    )

    assert create_response.status_code == 201

    job_id = create_response.json()["job_id"]
    job_dir = jobs_dir / job_id

    sample_file = (
        job_dir
        / "data/input/samples/sample.parquet"
    )
    output_file = (
        job_dir
        / "data/output/result.parquet"
    )
    log_file = (
        job_dir
        / "logs/pipeline.log"
    )
    temporary_file = (
        job_dir
        / "data/output/incomplete.uploading"
    )

    sample_file.write_bytes(b"sample")
    output_file.write_bytes(b"result")
    log_file.write_text(
        "pipeline log\n",
        encoding="utf-8",
    )
    temporary_file.write_bytes(b"incomplete")

    response = client.get(
        f"/api/v1/jobs/{job_id}/files"
    )

    assert response.status_code == 200

    files = {
        item["relative_path"]: item
        for item in response.json()
    }

    assert "job.json" in files
    assert files["job.json"]["category"] == "metadata"

    assert (
        files["data/input/samples/sample.parquet"]
        ["category"]
        == "input"
    )

    assert (
        files["data/output/result.parquet"]
        ["category"]
        == "output"
    )

    assert (
        files["logs/pipeline.log"]["category"]
        == "log"
    )

    assert (
        "data/output/incomplete.uploading"
        not in files
    )


def test_list_unknown_job_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.get(
        "/api/v1/jobs/job-inexistant/files"
    )

    assert response.status_code == 404
