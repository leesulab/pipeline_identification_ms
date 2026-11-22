"""Validation des configurations de pipeline."""

from math import isclose
from typing import Any, Dict, List, Tuple

from api.pipeline_schema import build_pipeline_schema


Configuration = Dict[str, Dict[str, Any]]


def _set_nested_value(
    target: Dict[str, Any],
    path: str,
    value: Any,
) -> None:
    """Convertit un chemin pointé en dictionnaire imbriqué."""
    parts = path.split(".")
    current = target

    for part in parts[:-1]:
        current = current.setdefault(part, {})

    current[parts[-1]] = value


def _valid_type(
    value: Any,
    expected_type: str,
) -> bool:
    """Vérifie strictement le type JSON attendu."""
    if expected_type == "boolean":
        return isinstance(value, bool)

    if expected_type == "integer":
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
        )

    if expected_type == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )

    if expected_type == "string":
        return isinstance(value, str)

    return False


def validate_pipeline_configuration(
    configuration: Configuration,
) -> Tuple[Configuration, List[str]]:
    """
    Valide une configuration partielle.

    Les valeurs absentes sont remplacées par les valeurs par défaut.
    La configuration normalisée utilise des dictionnaires imbriqués.
    """
    schema = build_pipeline_schema()
    normalized: Configuration = {}
    errors: List[str] = []

    known_sections = {
        section["id"]
        for section in schema["sections"]
    }

    for section_id in configuration:
        if section_id not in known_sections:
            errors.append(
                f"Section inconnue : {section_id}."
            )

    for section in schema["sections"]:
        section_id = section["id"]
        submitted = configuration.get(section_id, {})
        normalized_section: Dict[str, Any] = {}

        known_paths = {
            parameter["path"]
            for parameter in section["parameters"]
        }

        for path in submitted:
            if path not in known_paths:
                errors.append(
                    f"{section_id}.{path} : paramètre inconnu."
                )

        for parameter in section["parameters"]:
            path = parameter["path"]
            value = submitted.get(
                path,
                parameter["default"],
            )
            full_path = f"{section_id}.{path}"

            if not _valid_type(
                value,
                parameter["type"],
            ):
                errors.append(
                    f"{full_path} : type invalide, "
                    f"{parameter['type']} attendu."
                )
                continue

            choices = parameter.get("choices")

            if choices and value not in choices:
                errors.append(
                    f"{full_path} : valeur non autorisée. "
                    f"Choix : {', '.join(choices)}."
                )
                continue

            minimum = parameter.get("minimum")
            maximum = parameter.get("maximum")

            if minimum is not None and value < minimum:
                errors.append(
                    f"{full_path} : valeur minimale {minimum}."
                )
                continue

            if maximum is not None and value > maximum:
                errors.append(
                    f"{full_path} : valeur maximale {maximum}."
                )
                continue

            _set_nested_value(
                normalized_section,
                path,
                value,
            )

        normalized[section_id] = normalized_section

    identification = normalized.get(
        "IDENTIFICATION",
        {},
    )
    weights = identification.get("weights", {})

    if len(weights) == 3:
        weight_sum = sum(weights.values())

        if not isclose(
            weight_sum,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            errors.append(
                "IDENTIFICATION.weights : la somme des "
                f"poids doit être égale à 1, valeur {weight_sum:.6f}."
            )

    return normalized, errors
