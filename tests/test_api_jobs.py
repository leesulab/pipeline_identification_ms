"""Tests de création et de consultation des jobs."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_create_and_get_job(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.post(
        "/api/v1/jobs",
        json={
            "steps": [
                "file_discovery",
                "blanks",
            ],
            "parameters": {
                "project": "test-api",
            },
        },
    )

    assert response.status_code == 201

    created_job = response.json()
    job_id = created_job["job_id"]

    assert created_job["status"] == "created"
    assert created_job["steps"] == [
        "file_discovery",
        "blanks",
    ]
    assert created_job["progress"] == 0.0
    parameters = created_job["parameters"]

    assert parameters["project"] == "test-api"

    pipeline_configuration = parameters[
        "pipeline_configuration"
    ]

    assert len(pipeline_configuration) == 9
    assert (
        pipeline_configuration["PEAK_DETECTION"]
        ["threshold"]
        == 100
    )
    assert (
        pipeline_configuration["IDENTIFICATION"]
        ["weights"]
        == {
            "mz": 0.4,
            "ccs": 0.4,
            "rt": 0.2,
        }
    )

    job_dir = tmp_path / "jobs" / job_id
    job_file = job_dir / "job.json"

    assert job_file.exists()
    assert (job_dir / "data/input/samples").is_dir()
    assert (job_dir / "data/input/blanks").is_dir()
    assert (job_dir / "logs").is_dir()
    assert (job_dir / "state").is_dir()

    stored_job = json.loads(
        job_file.read_text(encoding="utf-8")
    )

    assert stored_job["job_id"] == job_id

    get_response = client.get(
        f"/api/v1/jobs/{job_id}"
    )

    assert get_response.status_code == 200
    assert get_response.json() == created_job


def test_create_job_normalizes_step_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.post(
        "/api/v1/jobs",
        json={
            "steps": [
                "categories",
                "file_discovery",
                "blanks",
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["steps"] == [
        "file_discovery",
        "blanks",
        "categories",
    ]


def test_create_job_rejects_unknown_step(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.post(
        "/api/v1/jobs",
        json={
            "steps": ["unknown_step"],
        },
    )

    assert response.status_code == 422
    assert "unknown_step" in response.json()["detail"]


def test_get_unknown_job_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.get(
        "/api/v1/jobs/job-inexistant"
    )

    assert response.status_code == 404
