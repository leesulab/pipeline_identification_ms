"""Tests de l’application isolée des configurations."""

from pathlib import Path

import pytest

from api.pipeline_runtime import (
    pipeline_configuration_scope,
)
from scripts.config.config import Config


def test_scope_applies_and_restores_configuration() -> None:
    original_threshold = Config.PEAK_DETECTION.threshold
    original_weights = dict(
        Config.IDENTIFICATION.weights
    )

    with pipeline_configuration_scope(
        {
            "PEAK_DETECTION": {
                "threshold": 350,
            },
            "IDENTIFICATION": {
                "weights": {
                    "mz": 0.5,
                    "ccs": 0.3,
                    "rt": 0.2,
                },
            },
        }
    ):
        assert Config.PEAK_DETECTION.threshold == 350
        assert Config.IDENTIFICATION.weights == {
            "mz": 0.5,
            "ccs": 0.3,
            "rt": 0.2,
        }

    assert (
        Config.PEAK_DETECTION.threshold
        == original_threshold
    )
    assert Config.IDENTIFICATION.weights == original_weights


def test_scope_restores_paths_modified_by_runner(
    tmp_path: Path,
) -> None:
    original_base_dir = Config.PATHS.BASE_DIR

    with pipeline_configuration_scope({}):
        Config.set_base_dir(tmp_path)

        assert Config.PATHS.BASE_DIR == tmp_path.resolve()

    assert Config.PATHS.BASE_DIR == original_base_dir


def test_scope_restores_configuration_after_error() -> None:
    original_workers = (
        Config.PROCESSING.parallel_max_workers
    )

    with pytest.raises(RuntimeError):
        with pipeline_configuration_scope(
            {
                "PROCESSING": {
                    "parallel_max_workers": 8,
                },
            }
        ):
            assert (
                Config.PROCESSING.parallel_max_workers
                == 8
            )

            raise RuntimeError("Erreur simulée")

    assert (
        Config.PROCESSING.parallel_max_workers
        == original_workers
    )


def test_scope_rejects_unknown_sections() -> None:
    with pytest.raises(
        ValueError,
        match="Section de configuration inconnue",
    ):
        with pipeline_configuration_scope(
            {
                "UNKNOWN": {
                    "value": 1,
                },
            }
        ):
            pass
