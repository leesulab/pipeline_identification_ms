"""Tests de la route de lancement des jobs."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_run_file_discovery_job(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    create_response = client.post(
        "/api/v1/jobs",
        json={
            "steps": ["file_discovery"],
        },
    )

    assert create_response.status_code == 201
    job_id = create_response.json()["job_id"]

    run_response = client.post(
        f"/api/v1/jobs/{job_id}/run"
    )

    assert run_response.status_code == 202

    # TestClient attend aussi la fin des BackgroundTasks.
    status_response = client.get(
        f"/api/v1/jobs/{job_id}"
    )

    assert status_response.status_code == 200

    completed_job = status_response.json()

    assert completed_job["status"] == "success"
    assert completed_job["progress"] == 1.0
    assert completed_job["error"] is None
    assert completed_job["result"]["status"] == "success"
    assert completed_job["result"]["steps"] == [
        "file_discovery"
    ]
    assert completed_job["result"]["sample_count"] == 0


def test_run_job_with_missing_calibration_records_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    create_response = client.post(
        "/api/v1/jobs",
        json={
            "steps": ["calibration"],
        },
    )

    job_id = create_response.json()["job_id"]

    run_response = client.post(
        f"/api/v1/jobs/{job_id}/run"
    )

    assert run_response.status_code == 202

    status_response = client.get(
        f"/api/v1/jobs/{job_id}"
    )

    failed_job = status_response.json()

    assert failed_job["status"] == "error"
    assert failed_job["result"] is None
    assert failed_job["completed_at"] is not None
    assert failed_job["error"]["type"] == "FileNotFoundError"
    assert "CCS_calibration_data.csv" in (
        failed_job["error"]["message"]
    )


def test_run_unknown_job_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.post(
        "/api/v1/jobs/job-inexistant/run"
    )

    assert response.status_code == 404
