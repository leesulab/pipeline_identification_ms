"""Tests de la liste persistante des jobs."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_list_jobs_newest_first(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )

    first_response = client.post(
        "/api/v1/jobs",
        json={"steps": ["file_discovery"]},
    )

    second_response = client.post(
        "/api/v1/jobs",
        json={"steps": ["blanks"]},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_job = first_response.json()
    second_job = second_response.json()

    response = client.get("/api/v1/jobs")

    assert response.status_code == 200

    jobs = response.json()

    assert len(jobs) == 2
    assert jobs[0]["job_id"] == second_job["job_id"]
    assert jobs[1]["job_id"] == first_job["job_id"]


def test_list_jobs_ignores_invalid_job_file(
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

    invalid_job_dir = jobs_dir / "job-corrompu"
    invalid_job_dir.mkdir(parents=True)

    invalid_job_file = invalid_job_dir / "job.json"
    invalid_job_file.write_text(
        "{json invalide",
        encoding="utf-8",
    )

    response = client.get("/api/v1/jobs")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_jobs_when_directory_is_absent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs-absents"),
    )

    response = client.get("/api/v1/jobs")

    assert response.status_code == 200
    assert response.json() == []
