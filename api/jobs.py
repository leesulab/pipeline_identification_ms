"""Création et stockage persistant des jobs de pipeline."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
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
