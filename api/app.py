"""Application FastAPI exposant la pipeline d'identification MS."""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from api.jobs import create_job, read_job
from main import PIPELINE_STEPS, normalize_steps


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
    error: Optional[str]
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
