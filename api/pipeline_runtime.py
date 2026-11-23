"""Application isolée d’une configuration pendant un job."""

from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from typing import Any, Dict, Iterator, Optional

from scripts.config.config import Config


CONFIGURATION_SECTIONS = (
    "PEAK_DETECTION",
    "INTRA_CLUSTERING",
    "BLANK_REPLICATE",
    "FEATURE_ALIGNMENT",
    "BLANK_SUBTRACTION",
    "REPLICATE",
    "IDENTIFICATION",
    "MS2_EXTRACTION",
    "PROCESSING",
)

_PIPELINE_CONFIGURATION_LOCK = RLock()


def _snapshot_config() -> Dict[str, Any]:
    """Copie les chemins et les neuf sections configurables."""
    snapshot = {
        "PATHS": deepcopy(Config.PATHS),
    }

    for section_id in CONFIGURATION_SECTIONS:
        snapshot[section_id] = deepcopy(
            getattr(Config, section_id)
        )

    return snapshot


def _restore_config(
    snapshot: Dict[str, Any],
) -> None:
    """Restaure intégralement la configuration globale."""
    Config.PATHS = snapshot["PATHS"]

    for section_id in CONFIGURATION_SECTIONS:
        setattr(
            Config,
            section_id,
            snapshot[section_id],
        )


def apply_pipeline_configuration(
    configuration: Optional[
        Dict[str, Dict[str, Any]]
    ],
) -> None:
    """Applique une configuration normalisée aux dataclasses."""
    if not configuration:
        return

    for section_id, values in configuration.items():
        if section_id not in CONFIGURATION_SECTIONS:
            raise ValueError(
                f"Section de configuration inconnue : "
                f"{section_id}."
            )

        config_object = getattr(Config, section_id)

        for field_name, field_value in values.items():
            if not hasattr(config_object, field_name):
                raise ValueError(
                    f"Paramètre inconnu : "
                    f"{section_id}.{field_name}."
                )

            setattr(
                config_object,
                field_name,
                deepcopy(field_value),
            )


@contextmanager
def pipeline_configuration_scope(
    configuration: Optional[
        Dict[str, Dict[str, Any]]
    ],
) -> Iterator[None]:
    """
    Sérialise les exécutions et restaure Config après le job.

    Le verrou couvre toute l’exécution, car Config et Config.PATHS
    sont globaux et utilisés directement par les processeurs.
    """
    with _PIPELINE_CONFIGURATION_LOCK:
        snapshot = _snapshot_config()

        try:
            apply_pipeline_configuration(configuration)
            yield
        finally:
            _restore_config(snapshot)
