"""Génération du schéma de configuration de la pipeline."""

from dataclasses import fields
from typing import Any, Dict, List, Type

from api.pipeline_metadata import (
    get_parameter_metadata,
)

from scripts.config.config import (
    BlankReplicateConfig,
    BlankSubtractionConfig,
    FeatureAlignmentConfig,
    IdentificationConfig,
    IntraClusteringConfig,
    MS2ExtractionConfig,
    PeakDetectionConfig,
    ProcessingConfig,
    ReplicateConfig,
)


CONFIGURATION_SECTIONS = [
    (
        "PEAK_DETECTION",
        "Détection des pics",
        PeakDetectionConfig,
    ),
    (
        "INTRA_CLUSTERING",
        "Clustering intra-échantillon",
        IntraClusteringConfig,
    ),
    (
        "BLANK_REPLICATE",
        "Réplicats blanks",
        BlankReplicateConfig,
    ),
    (
        "FEATURE_ALIGNMENT",
        "Alignement des features",
        FeatureAlignmentConfig,
    ),
    (
        "BLANK_SUBTRACTION",
        "Soustraction du blank",
        BlankSubtractionConfig,
    ),
    (
        "REPLICATE",
        "Réplicats échantillons",
        ReplicateConfig,
    ),
    (
        "IDENTIFICATION",
        "Identification",
        IdentificationConfig,
    ),
    (
        "MS2_EXTRACTION",
        "Extraction MS2",
        MS2ExtractionConfig,
    ),
    (
        "PROCESSING",
        "Traitement général",
        ProcessingConfig,
    ),
]


def parameter_type(value: Any) -> str:
    """Convertit une valeur Python en type de formulaire."""
    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, int):
        return "integer"

    if isinstance(value, float):
        return "number"

    return "string"


def default_label(name: str) -> str:
    """Produit un libellé temporaire lisible."""
    return name.replace("_", " ").capitalize()


def flatten_parameter(
    name: str,
    value: Any,
) -> List[Dict[str, Any]]:
    """Déplie les dictionnaires en chemins pointés."""
    if isinstance(value, dict):
        parameters = []

        for child_name, child_value in value.items():
            parameters.extend(
                flatten_parameter(
                    f"{name}.{child_name}",
                    child_value,
                )
            )

        return parameters

    metadata = get_parameter_metadata(name)

    parameter = {
        "path": name,
        "label": metadata.pop(
            "label",
            default_label(
                name.split(".")[-1]
            ),
        ),
        "type": parameter_type(value),
        "default": value,
        "required": True,
    }

    parameter.update(metadata)

    return [parameter]


def build_section_schema(
    section_id: str,
    label: str,
    config_class: Type[Any],
) -> Dict[str, Any]:
    """Construit le schéma d’une dataclass de configuration."""
    instance = config_class()
    parameters = []

    for config_field in fields(instance):
        parameters.extend(
            flatten_parameter(
                config_field.name,
                getattr(instance, config_field.name),
            )
        )

    return {
        "id": section_id,
        "label": label,
        "class_name": config_class.__name__,
        "parameters": parameters,
    }


def build_pipeline_schema() -> Dict[str, Any]:
    """Construit le contrat complet consommé par Tauri."""
    sections = [
        build_section_schema(
            section_id,
            label,
            config_class,
        )
        for (
            section_id,
            label,
            config_class,
        ) in CONFIGURATION_SECTIONS
    ]

    return {
        "version": 1,
        "sections": sections,
    }
