"""Application FastAPI exposant la pipeline d'identification MS."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from api.jobs import (
    create_job,
    get_job_dir,
    read_job,
    run_job,
)
from main import (
    PIPELINE_STEPS,
    normalize_steps,
    run_pipeline,
)


class HealthResponse(BaseModel):
    """Réponse du contrôle de santé de l'API."""

    status: str
    service: str
    version: str


class JobCreateRequest(BaseModel):
    """Paramètres de création d'un job."""

    steps: Optional[List[str]] = None
    parameters: Dict[str, Any] = Field(
        default_factory=dict
    )


class FileUploadResponse(BaseModel):
    """Résultat du dépôt d'un fichier dans un job."""

    job_id: str
    destination: str
    filename: str
    size_bytes: int
    relative_path: str


class JobResponse(BaseModel):
    """État persistant d'un job."""

    job_id: str
    status: str
    steps: List[str]
    parameters: Dict[str, Any]
    progress: float
    current_step: Optional[str]
    message: str
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    working_dir: str


app = FastAPI(
    title="Pipeline Identification MS API",
    description=(
        "API d'exécution de la pipeline d'identification HRMS "
        "utilisée par LASSO."
    ),
    version="0.2.0",
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Système"],
)
def health() -> HealthResponse:
    """Vérifie que le service HTTP fonctionne."""
    return HealthResponse(
        status="ok",
        service="pipeline-identification-ms",
        version=app.version,
    )


@app.get(
    "/api/v1/steps",
    response_model=List[str],
    tags=["Pipeline"],
)
def list_steps() -> List[str]:
    """Liste les étapes disponibles dans leur ordre canonique."""
    return list(PIPELINE_STEPS)


@app.post(
    "/api/v1/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Jobs"],
)
def create_pipeline_job(
    request: JobCreateRequest,
) -> JobResponse:
    """Crée un job sans encore lancer la pipeline."""
    try:
        selected_steps = normalize_steps(request.steps)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    job = create_job(
        steps=selected_steps,
        parameters=request.parameters,
    )

    return JobResponse(**job)


UPLOAD_DESTINATIONS = {
    "samples": {
        "directory": "data/input/samples",
        "extensions": {".parquet"},
    },
    "blanks": {
        "directory": "data/input/blanks",
        "extensions": {".parquet"},
    },
    "calibration": {
        "directory": "data/input/calibration",
        "extensions": {".csv"},
    },
    "databases": {
        "directory": "data/input/databases",
        "extensions": {".h5", ".hdf5"},
    },
}

DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


@app.post(
    "/api/v1/jobs/{job_id}/files",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Fichiers"],
)
async def upload_job_file(
    job_id: str,
    destination: str = Form(...),
    uploaded_file: UploadFile = File(...),
) -> FileUploadResponse:
    """Dépose un fichier d'entrée dans l'espace isolé du job."""
    try:
        job = read_job(job_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    if job["status"] not in {"created", "error"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Les fichiers ne peuvent être modifiés que pour "
                "un job créé ou en erreur."
            ),
        )

    destination_config = UPLOAD_DESTINATIONS.get(
        destination
    )

    if destination_config is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Destination inconnue. Valeurs autorisées : "
                + ", ".join(UPLOAD_DESTINATIONS)
            ),
        )

    raw_filename = uploaded_file.filename or ""
    safe_filename = Path(raw_filename).name

    if (
        not safe_filename
        or safe_filename in {".", ".."}
        or safe_filename != raw_filename
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom de fichier invalide.",
        )

    extension = Path(safe_filename).suffix.lower()
    allowed_extensions = destination_config[
        "extensions"
    ]

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Extension {extension or '(absente)'} interdite "
                f"pour {destination}. Extensions autorisées : "
                + ", ".join(sorted(allowed_extensions))
            ),
        )

    max_upload_bytes = int(
        os.environ.get(
            "PIPELINE_MAX_UPLOAD_BYTES",
            DEFAULT_MAX_UPLOAD_BYTES,
        )
    )

    job_dir = get_job_dir(job_id)
    destination_dir = (
        job_dir / destination_config["directory"]
    )
    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    target_file = destination_dir / safe_filename
    temporary_file = destination_dir / (
        safe_filename + ".uploading"
    )

    size_bytes = 0
    chunk_size = 1024 * 1024

    try:
        with temporary_file.open("wb") as output:
            while True:
                chunk = await uploaded_file.read(
                    chunk_size
                )

                if not chunk:
                    break

                size_bytes += len(chunk)

                if size_bytes > max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            "Fichier trop volumineux. "
                            f"Limite : {max_upload_bytes} octets."
                        ),
                    )

                output.write(chunk)

        temporary_file.replace(target_file)

    except Exception:
        temporary_file.unlink(missing_ok=True)
        raise

    finally:
        await uploaded_file.close()

    relative_path = str(
        target_file.relative_to(job_dir)
    )

    return FileUploadResponse(
        job_id=job_id,
        destination=destination,
        filename=safe_filename,
        size_bytes=size_bytes,
        relative_path=relative_path,
    )


def execute_job_in_background(job_id: str) -> None:
    """Exécute un job et conserve l'erreur dans son état persistant."""
    try:
        run_job(
            job_id,
            run_pipeline,
        )
    except Exception:
        # run_job a déjà persisté le statut et le détail de l'erreur.
        return


@app.post(
    "/api/v1/jobs/{job_id}/run",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
)
def start_pipeline_job(
    job_id: str,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """Planifie l'exécution d'un job existant."""
    try:
        job = read_job(job_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    if job["status"] == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le job {job_id} est déjà en cours.",
        )

    if job["status"] == "success":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le job {job_id} est déjà terminé.",
        )

    background_tasks.add_task(
        execute_job_in_background,
        job_id,
    )

    return JobResponse(**job)


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobResponse,
    tags=["Jobs"],
)
def get_pipeline_job(job_id: str) -> JobResponse:
    """Consulte l'état persistant d'un job."""
    try:
        job = read_job(job_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return JobResponse(**job)
