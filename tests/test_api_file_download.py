"""Tests du téléchargement sécurisé des fichiers de jobs."""

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


def test_download_job_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )

    job_id = create_test_job()
    expected_content = b"feature-results"

    result_file = (
        jobs_dir
        / job_id
        / "data/output/features.parquet"
    )

    result_file.write_bytes(expected_content)

    response = client.get(
        f"/api/v1/jobs/{job_id}/files/"
        "data/output/features.parquet"
    )

    assert response.status_code == 200
    assert response.content == expected_content
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="features.parquet"'
    )


def test_download_missing_file_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job_id = create_test_job()

    response = client.get(
        f"/api/v1/jobs/{job_id}/files/"
        "data/output/missing.parquet"
    )

    assert response.status_code == 404


def test_resolver_rejects_parent_traversal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job_id = create_test_job()

    from api.app import resolve_job_file
    from fastapi import HTTPException

    try:
        resolve_job_file(
            job_id,
            "../../etc/passwd",
        )
    except HTTPException as error:
        assert error.status_code == 400
    else:
        raise AssertionError(
            "La traversée de répertoire aurait dû être refusée"
        )


def test_download_rejects_temporary_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    jobs_dir = tmp_path / "jobs"

    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(jobs_dir),
    )

    job_id = create_test_job()

    temporary_file = (
        jobs_dir
        / job_id
        / "data/output/result.uploading"
    )

    temporary_file.write_bytes(b"incomplete")

    response = client.get(
        f"/api/v1/jobs/{job_id}/files/"
        "data/output/result.uploading"
    )

    assert response.status_code == 404
