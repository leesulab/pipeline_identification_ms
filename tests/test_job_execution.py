"""Tests de l'exécution persistante des jobs."""

from pathlib import Path

import pytest

from api.jobs import (
    create_job,
    read_job,
    run_job,
)


def test_run_job_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["file_discovery"],
    )

    callback_states = []

    def fake_pipeline_runner(
        *,
        base_dir,
        steps,
        progress_callback,
    ):
        assert base_dir == job["working_dir"]
        assert steps == ["file_discovery"]

        progress_callback({
            "step": "file_discovery",
            "status": "running",
            "message": "Détection des fichiers",
            "progress": 0.20,
        })

        callback_states.append(
            read_job(job["job_id"])
        )

        return {
            "status": "success",
            "steps": steps,
            "sample_count": 0,
        }

    completed_job = run_job(
        job["job_id"],
        fake_pipeline_runner,
    )

    assert callback_states[0]["status"] == "running"
    assert callback_states[0]["current_step"] == (
        "file_discovery"
    )
    assert callback_states[0]["progress"] == 0.20

    assert completed_job["status"] == "success"
    assert completed_job["progress"] == 1.0
    assert completed_job["current_step"] is None
    assert completed_job["completed_at"] is not None
    assert completed_job["error"] is None
    assert completed_job["result"] == {
        "status": "success",
        "steps": ["file_discovery"],
        "sample_count": 0,
    }


def test_run_job_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["calibration"],
    )

    def failing_pipeline_runner(**kwargs):
        raise FileNotFoundError(
            "Calibration absente"
        )

    with pytest.raises(
        FileNotFoundError,
        match="Calibration absente",
    ):
        run_job(
            job["job_id"],
            failing_pipeline_runner,
        )

    failed_job = read_job(job["job_id"])

    assert failed_job["status"] == "error"
    assert failed_job["completed_at"] is not None
    assert failed_job["result"] is None
    assert failed_job["error"] == {
        "type": "FileNotFoundError",
        "message": "Calibration absente",
    }
