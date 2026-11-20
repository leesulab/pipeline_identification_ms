"""Tests de récupération des jobs interrompus."""

from pathlib import Path

from api.jobs import (
    create_job,
    read_job,
    recover_interrupted_jobs,
    update_job,
)


def test_recover_running_job_as_interrupted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["samples"],
    )

    update_job(
        job["job_id"],
        status="running",
        progress=0.4,
        current_step="samples",
        message="Traitement des échantillons",
        started_at="2026-11-20T18:00:00+00:00",
    )

    recovered_jobs = recover_interrupted_jobs()

    assert len(recovered_jobs) == 1

    recovered_job = read_job(job["job_id"])

    assert recovered_job["status"] == "interrupted"
    assert recovered_job["progress"] == 0.4
    assert recovered_job["current_step"] is None
    assert recovered_job["completed_at"] is not None
    assert recovered_job["result"] is None
    assert recovered_job["error"] == {
        "type": "JobInterruptedError",
        "message": (
            "Le backend a été arrêté pendant "
            "l'exécution du job."
        ),
    }


def test_recovery_does_not_modify_completed_jobs(
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

    update_job(
        job["job_id"],
        status="success",
        progress=1.0,
        message="Pipeline terminée",
        result={
            "status": "success",
        },
    )

    recovered_jobs = recover_interrupted_jobs()

    assert recovered_jobs == []
    assert read_job(job["job_id"])["status"] == "success"


def test_recovery_is_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    job = create_job(
        steps=["samples"],
    )

    update_job(
        job["job_id"],
        status="running",
    )

    assert len(recover_interrupted_jobs()) == 1
    assert recover_interrupted_jobs() == []
