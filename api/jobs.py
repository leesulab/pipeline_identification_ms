"""Création et stockage persistant des jobs de pipeline."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.pipeline_runtime import (
    pipeline_configuration_scope,
)

from uuid import uuid4


DEFAULT_JOBS_DIR = Path(__file__).parent.parent / "jobs"


def get_jobs_dir() -> Path:
    """Retourne le dossier racine des jobs."""
    configured_dir = os.environ.get("PIPELINE_JOBS_DIR")

    if configured_dir:
        return Path(configured_dir).expanduser().resolve()

    return DEFAULT_JOBS_DIR.resolve()


def get_job_dir(job_id: str) -> Path:
    """Retourne le dossier d'un job."""
    return get_jobs_dir() / job_id


def get_job_file(job_id: str) -> Path:
    """Retourne le fichier JSON décrivant un job."""
    return get_job_dir(job_id) / "job.json"


def utc_now() -> str:
    """Retourne l'heure UTC au format ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def write_job(job: Dict[str, Any]) -> None:
    """Écrit atomiquement le fichier d'état d'un job."""
    job_dir = get_job_dir(job["job_id"])
    job_dir.mkdir(parents=True, exist_ok=True)

    job_file = job_dir / "job.json"
    temporary_file = job_dir / "job.json.tmp"

    temporary_file.write_text(
        json.dumps(
            job,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(job_file)


def create_job(
    steps: List[str],
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Crée un job persistant sans lancer son exécution."""
    job_id = str(uuid4())
    created_at = utc_now()
    job_dir = get_job_dir(job_id)

    for relative_dir in [
        "data/input/samples",
        "data/input/blanks",
        "data/input/calibration",
        "data/input/databases",
        "data/intermediate/samples",
        "data/output",
        "logs",
        "state",
    ]:
        (job_dir / relative_dir).mkdir(
            parents=True,
            exist_ok=True,
        )

    job = {
        "job_id": job_id,
        "status": "created",
        "steps": steps,
        "parameters": parameters or {},
        "progress": 0.0,
        "current_step": None,
        "message": "Job créé",
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "working_dir": str(job_dir),
    }

    write_job(job)
    return job


def read_job(job_id: str) -> Dict[str, Any]:
    """Charge l'état persistant d'un job."""
    job_file = get_job_file(job_id)

    if not job_file.exists():
        raise FileNotFoundError(
            f"Job introuvable : {job_id}"
        )

    return json.loads(
        job_file.read_text(encoding="utf-8")
    )


def update_job(
    job_id: str,
    **changes: Any,
) -> Dict[str, Any]:
    """Met à jour puis persiste l'état d'un job."""
    job = read_job(job_id)
    job.update(changes)
    job["updated_at"] = utc_now()
    write_job(job)
    return job


def run_job(
    job_id: str,
    pipeline_runner,
) -> Dict[str, Any]:
    """Exécute un job avec le moteur de pipeline fourni."""
    job = read_job(job_id)

    if job["status"] == "running":
        raise RuntimeError(
            f"Le job {job_id} est déjà en cours d'exécution."
        )

    if job["status"] == "success":
        raise RuntimeError(
            f"Le job {job_id} est déjà terminé avec succès."
        )

    started_at = utc_now()

    update_job(
        job_id,
        status="running",
        progress=0.0,
        current_step=None,
        message="Démarrage de la pipeline",
        started_at=started_at,
        completed_at=None,
        error=None,
        result=None,
    )

    def progress_callback(event: Dict[str, Any]) -> None:
        progress = event.get("progress")

        changes = {
            "status": (
                "error"
                if event.get("status") == "error"
                else "running"
            ),
            "current_step": event.get("step"),
            "message": event.get("message", ""),
        }

        if progress is not None:
            changes["progress"] = float(progress)

        update_job(job_id, **changes)

    try:
        pipeline_configuration = (
            job.get("parameters", {}).get(
                "pipeline_configuration"
            )
        )

        with pipeline_configuration_scope(
            pipeline_configuration
        ):
            result = pipeline_runner(
                base_dir=job["working_dir"],
                steps=job["steps"],
                progress_callback=progress_callback,
            )

        return update_job(
            job_id,
            status="success",
            progress=1.0,
            current_step=None,
            message="Pipeline terminée",
            completed_at=utc_now(),
            error=None,
            result=result,
        )

    except Exception as error:
        update_job(
            job_id,
            status="error",
            current_step=None,
            message=str(error),
            completed_at=utc_now(),
            error={
                "type": type(error).__name__,
                "message": str(error),
            },
            result=None,
        )
        raise


def list_jobs() -> List[Dict[str, Any]]:
    """Liste les jobs persistants, du plus récent au plus ancien."""
    jobs_dir = get_jobs_dir()

    if not jobs_dir.exists():
        return []

    jobs = []

    for job_file in jobs_dir.glob("*/job.json"):
        try:
            job = json.loads(
                job_file.read_text(encoding="utf-8")
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        jobs.append(job)

    jobs.sort(
        key=lambda job: job.get("created_at", ""),
        reverse=True,
    )

    return jobs


def recover_interrupted_jobs() -> List[Dict[str, Any]]:
    """
    Marque comme interrompus les jobs laissés en cours par un ancien
    processus du backend.
    """
    recovered_jobs = []

    for job in list_jobs():
        if job.get("status") != "running":
            continue

        job_id = job.get("job_id")

        if not isinstance(job_id, str) or not job_id:
            continue

        recovered_job = update_job(
            job_id,
            status="interrupted",
            progress=job.get("progress", 0.0),
            current_step=None,
            message=(
                "Le backend a été arrêté pendant "
                "l'exécution du job."
            ),
            completed_at=utc_now(),
            error={
                "type": "JobInterruptedError",
                "message": (
                    "Le backend a été arrêté pendant "
                    "l'exécution du job."
                ),
            },
            result=None,
        )

        recovered_jobs.append(recovered_job)

    return recovered_jobs
