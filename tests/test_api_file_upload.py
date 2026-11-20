"""Tests du dépôt des fichiers d'entrée."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def create_test_job() -> str:
    response = client.post(
        "/api/v1/jobs",
        json={"steps": ["file_discovery"]},
    )

    assert response.status_code == 201
    return response.json()["job_id"]


def test_upload_sample_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )

    job_id = create_test_job()
    file_content = b"parquet-test-content"

    response = client.post(
        f"/api/v1/jobs/{job_id}/files",
        data={"destination": "samples"},
        files={
            "uploaded_file": (
                "sample_replicate_1.parquet",
                file_content,
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 201

    result = response.json()

    assert result == {
        "job_id": job_id,
        "destination": "samples",
        "filename": "sample_replicate_1.parquet",
        "size_bytes": len(file_content),
        "relative_path": (
            "data/input/samples/"
            "sample_replicate_1.parquet"
        ),
    }

    stored_file = (
        jobs_dir
        / job_id
        / result["relative_path"]
    )

    assert stored_file.read_bytes() == file_content


def test_upload_rejects_invalid_extension(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job_id = create_test_job()

    response = client.post(
        f"/api/v1/jobs/{job_id}/files",
        data={"destination": "calibration"},
        files={
            "uploaded_file": (
                "calibration.exe",
                b"invalid",
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 415


def test_upload_rejects_unknown_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job_id = create_test_job()

    response = client.post(
        f"/api/v1/jobs/{job_id}/files",
        data={"destination": "unknown"},
        files={
            "uploaded_file": (
                "sample.parquet",
                b"content",
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 422


def test_upload_enforces_size_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )
    monkeypatch.setenv(
        "PIPELINE_MAX_UPLOAD_BYTES",
        "5",
    )

    job_id = create_test_job()

    response = client.post(
        f"/api/v1/jobs/{job_id}/files",
        data={"destination": "samples"},
        files={
            "uploaded_file": (
                "sample.parquet",
                b"123456",
                "application/octet-stream",
            ),
        },
    )

    assert response.status_code == 413

    destination = (
        jobs_dir
        / job_id
        / "data/input/samples"
    )

    assert not (destination / "sample.parquet").exists()
    assert not (
        destination / "sample.parquet.uploading"
    ).exists()
