"""Format versionné des presets de configuration."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from api.pipeline_validation import (
    validate_pipeline_configuration,
)


PRESET_FORMAT_VERSION = 1
PIPELINE_SCHEMA_VERSION = 1


def utc_now() -> str:
    """Retourne une date UTC au format ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def build_default_preset() -> Dict[str, Any]:
    """Construit le preset officiel depuis les dataclasses."""
    configuration, errors = (
        validate_pipeline_configuration({})
    )

    if errors:
        raise RuntimeError(
            "Les valeurs par défaut de la pipeline "
            "sont invalides : "
            + " ".join(errors)
        )

    return {
        "format_version": PRESET_FORMAT_VERSION,
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "id": "default",
        "name": "Valeurs par défaut",
        "description": (
            "Configuration scientifique par défaut "
            "fournie par le moteur LASSO."
        ),
        "built_in": True,
        "created_at": None,
        "configuration": configuration,
    }


def validate_pipeline_preset(
    preset: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Valide et normalise un preset importé."""
    errors: List[str] = []

    if preset.get("format_version") != PRESET_FORMAT_VERSION:
        errors.append(
            "Version de format de preset incompatible."
        )

    if preset.get("schema_version") != PIPELINE_SCHEMA_VERSION:
        errors.append(
            "Version du schéma de pipeline incompatible."
        )

    name = preset.get("name")

    if not isinstance(name, str) or not name.strip():
        errors.append(
            "Le nom du preset est obligatoire."
        )

    raw_configuration = preset.get("configuration")

    if not isinstance(raw_configuration, dict):
        errors.append(
            "La configuration du preset est absente "
            "ou invalide."
        )
        raw_configuration = {}

    configuration, configuration_errors = (
        validate_pipeline_configuration(
            raw_configuration
        )
    )

    errors.extend(configuration_errors)

    if errors:
        return None, errors

    normalized = {
        "format_version": PRESET_FORMAT_VERSION,
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "id": preset.get("id"),
        "name": name.strip(),
        "description": str(
            preset.get("description", "")
        ).strip(),
        "built_in": False,
        "created_at": (
            preset.get("created_at")
            if isinstance(
                preset.get("created_at"),
                str,
            )
            else utc_now()
        ),
        "configuration": configuration,
    }

    return normalized, []
