"""Application FastAPI exposant la pipeline d'identification MS."""

import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from api.pipeline_schema import build_pipeline_schema
from api.pipeline_presets import (
    build_default_preset,
    validate_pipeline_preset,
)
from api.result_manifest import (
    build_result_manifest,
)
from api.table_preview import (
    DEFAULT_LIMIT,
    preview_table,
)

from api.pipeline_validation import (
    validate_pipeline_configuration,
)

from api.jobs import (
    create_job,
    get_job_dir,
    list_jobs,
    read_job,
    run_job,
)
from main import (
    PIPELINE_STEPS,
    normalize_steps,
    run_pipeline,
)


class PipelineParameterSchema(BaseModel):
    """Paramètre éditable d’une section de configuration."""

    path: str
    label: str
    type: str
    default: Any
    required: bool
    description: Optional[str] = None
    unit: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[str]] = None
    group: Optional[str] = None


class ConfigurationValidationRequest(BaseModel):
    """Configuration partielle envoyée par l’application."""

    configuration: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict
    )


class ConfigurationValidationResponse(BaseModel):
    """Résultat de validation et configuration normalisée."""

    valid: bool
    configuration: Dict[str, Dict[str, Any]]
    errors: List[str]


class PipelinePreset(BaseModel):
    """Preset versionné de configuration de pipeline."""

    format_version: int
    schema_version: int
    id: Optional[str] = None
    name: str
    description: str
    built_in: bool
    created_at: Optional[str]
    configuration: Dict[str, Dict[str, Any]]


class PipelinePresetValidationRequest(BaseModel):
    """Preset JSON à valider avant son import."""

    preset: Dict[str, Any]


class PipelinePresetValidationResponse(BaseModel):
    """Résultat de la validation d’un preset."""

    valid: bool
    preset: Optional[PipelinePreset] = None
    errors: List[str]


class PipelineSectionSchema(BaseModel):
    """Section configurable de la pipeline."""

    id: str
    label: str
    class_name: str
    parameters: List[PipelineParameterSchema]


class PipelineSchemaResponse(BaseModel):
    """Schéma dynamique consommé par l’application desktop."""

    version: int
    sections: List[PipelineSectionSchema]


class JobResultEntry(BaseModel):
    """Résultat scientifique présent dans un job."""

    id: str
    title: str
    group: str
    kind: str
    format: str
    relative_path: str
    size_bytes: int
    order: int


class TablePreviewColumn(BaseModel):
    """Colonne exposée dans l’aperçu tabulaire."""

    name: str
    type: str


class TablePreviewResponse(BaseModel):
    """Page de prévisualisation CSV ou Parquet."""

    result_id: str
    format: str
    columns: List[TablePreviewColumn]
    rows: List[Dict[str, Any]]
    offset: int
    limit: int
    returned: int
    total: int
    has_more: bool
    sort_by: Optional[str] = None
    sort_direction: Optional[str] = None


class JobResultManifest(BaseModel):
    """Manifeste versionné des résultats d’un job."""

    version: int
    job_id: str
    results: List[JobResultEntry]


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
    "/api/v1/pipeline/schema",
    response_model=PipelineSchemaResponse,
    tags=["Pipeline"],
)
def get_pipeline_schema() -> PipelineSchemaResponse:
    """Expose les sections, paramètres et valeurs par défaut."""
    return PipelineSchemaResponse(
        **build_pipeline_schema()
    )


@app.get(
    "/api/v1/pipeline/presets",
    response_model=List[PipelinePreset],
    tags=["Pipeline"],
)
def list_pipeline_presets() -> List[PipelinePreset]:
    """Liste les presets intégrés au moteur."""
    return [
        PipelinePreset(**build_default_preset())
    ]


@app.post(
    "/api/v1/pipeline/presets/validate",
    response_model=PipelinePresetValidationResponse,
    tags=["Pipeline"],
)
def validate_preset(
    request: PipelinePresetValidationRequest,
) -> PipelinePresetValidationResponse:
    """Valide et normalise un preset JSON importé."""
    normalized, errors = validate_pipeline_preset(
        request.preset
    )

    return PipelinePresetValidationResponse(
        valid=not errors,
        preset=(
            PipelinePreset(**normalized)
            if normalized is not None
            else None
        ),
        errors=errors,
    )


@app.post(
    "/api/v1/pipeline/configuration/validate",
    response_model=ConfigurationValidationResponse,
    tags=["Pipeline"],
)
def validate_configuration(
    request: ConfigurationValidationRequest,
) -> ConfigurationValidationResponse:
    """Valide et complète une configuration de pipeline."""
    normalized, errors = validate_pipeline_configuration(
        request.configuration
    )

    return ConfigurationValidationResponse(
        valid=not errors,
        configuration=normalized,
        errors=errors,
    )


@app.get(
    "/api/v1/steps",
    response_model=List[str],
    tags=["Pipeline"],
)
def list_steps() -> List[str]:
    """Liste les étapes disponibles dans leur ordre canonique."""
    return list(PIPELINE_STEPS)


@app.get(
    "/api/v1/jobs",
    response_model=List[JobResponse],
    tags=["Jobs"],
)
def list_pipeline_jobs() -> List[JobResponse]:
    """Liste les jobs persistants du plus récent au plus ancien."""
    return [
        JobResponse(**job)
        for job in list_jobs()
    ]


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

    parameters = dict(request.parameters)

    submitted_configuration = parameters.get(
        "pipeline_configuration",
        {},
    )

    normalized_configuration, configuration_errors = (
        validate_pipeline_configuration(
            submitted_configuration
        )
    )

    if configuration_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "La configuration de la pipeline "
                    "est invalide."
                ),
                "errors": configuration_errors,
            },
        )

    parameters["pipeline_configuration"] = (
        normalized_configuration
    )

    job = create_job(
        steps=selected_steps,
        parameters=parameters,
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


class JobFileResponse(BaseModel):
    """Métadonnées d'un fichier appartenant à un job."""

    relative_path: str
    size_bytes: int
    category: str


def classify_job_file(relative_path: Path) -> str:
    """Classe un fichier du job selon son emplacement."""
    path_text = relative_path.as_posix()

    if path_text.startswith("data/input/"):
        return "input"

    if path_text.startswith("data/intermediate/"):
        return "intermediate"

    if path_text.startswith("data/output/"):
        return "output"

    if path_text.startswith("logs/"):
        return "log"

    if path_text.startswith("state/"):
        return "state"

    return "metadata"


@app.get(
    "/api/v1/jobs/{job_id}/tables/{result_id}/preview",
    response_model=TablePreviewResponse,
    tags=["Résultats"],
)
def preview_job_table(
    job_id: str,
    result_id: str,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    columns: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_direction: Optional[str] = None,
) -> TablePreviewResponse:
    """Retourne une page d’une table scientifique."""
    try:
        job = read_job(job_id)

        selected_columns = (
            [
                value.strip()
                for value in columns.split(",")
                if value.strip()
            ]
            if columns
            else None
        )

        preview = preview_table(
            job_id=job_id,
            job_dir=Path(job["working_dir"]),
            result_id=result_id,
            offset=offset,
            limit=limit,
            columns=selected_columns,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return TablePreviewResponse(**preview)


@app.get(
    "/api/v1/jobs/{job_id}/results",
    response_model=JobResultManifest,
    tags=["Résultats"],
)
def get_job_results(
    job_id: str,
) -> JobResultManifest:
    """Retourne le manifeste scientifique des résultats."""
    try:
        job = read_job(job_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    manifest = build_result_manifest(
        job_id,
        Path(job["working_dir"]),
    )

    return JobResultManifest(**manifest)


@app.get(
    "/api/v1/jobs/{job_id}/files",
    response_model=List[JobFileResponse],
    tags=["Fichiers"],
)
def list_job_files(
    job_id: str,
) -> List[JobFileResponse]:
    """Listedans l'espace isolé du job."""
    try:
        read_job(job_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    job_dir = get_job_dir(job_id)
    files = []

    for path in sorted(job_dir.rglob("*")):
        if not path.is_file():
            continue

        if path.name.endswith(".uploading"):
            continue

        relative_path = path.relative_to(job_dir)

        files.append(
            JobFileResponse(
                relative_path=relative_path.as_posix(),
                size_bytes=path.stat().st_size,
                category=classify_job_file(
                    relative_path
                ),
            )
        )

    return files

def resolve_job_file(
    job_id: str,
    relative_path: str,
) -> Path:
    """Résout un fichier du job sans autoriser de sortie du dossier."""
    try:
        read_job(job_id)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    requested_path = Path(relative_path)

    if (
        requested_path.is_absolute()
        or not requested_path.parts
        or any(
            part in {"", ".", ".."}
            for part in requested_path.parts
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chemin de fichier invalide.",
        )

    job_dir = get_job_dir(job_id).resolve()
    target_file = (job_dir / requested_path).resolve()

    try:
        target_file.relative_to(job_dir)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le chemin demandé sort du dossier du job.",
        ) from error

    if (
        not target_file.exists()
        or not target_file.is_file()
        or target_file.name.endswith(".uploading")
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Fichier introuvable dans le job : "
                f"{relative_path}"
            ),
        )

    return target_file


@app.get(
    "/api/v1/jobs/{job_id}/files/{relative_path:path}",
    response_class=FileResponse,
    tags=["Fichiers"],
)
def download_job_file(
    job_id: str,
    relative_path: str,
) -> FileResponse:
    """Télécharge un fichier appartenant au job."""
    target_file = resolve_job_file(
        job_id,
        relative_path,
    )

    return FileResponse(
        path=target_file,
        filename=target_file.name,
        media_type="application/octet-stream",
    )


@app.middleware("http")
async def require_local_api_token(
    request: Request,
    call_next,
):
    """
    Protège les routes /api/v1 lorsque PIPELINE_API_TOKEN est défini.

    /health reste public afin que l'application Tauri puisse vérifier
    que le backend local est démarré.
    """
    expected_token = os.environ.get(
        "PIPELINE_API_TOKEN",
        "",
    )

    if (
        expected_token
        and request.url.path.startswith("/api/v1/")
    ):
        authorization = request.headers.get(
            "Authorization",
            "",
        )

        scheme, separator, provided_token = (
            authorization.partition(" ")
        )

        valid_token = (
            separator == " "
            and scheme.lower() == "bearer"
            and bool(provided_token)
            and secrets.compare_digest(
                provided_token,
                expected_token,
            )
        )

        if not valid_token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": (
                        "Jeton d'authentification local "
                        "absent ou invalide."
                    )
                },
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

    return await call_next(request)

TAURI_ALLOWED_ORIGINS = [
    # Serveur Vite utilisé par `tauri dev`.
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    # Origines possibles du protocole Tauri en production.
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=TAURI_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
    ],
)
