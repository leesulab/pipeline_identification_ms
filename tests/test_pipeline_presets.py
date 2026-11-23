"""Tests du format versionné des presets."""

from api.pipeline_presets import (
    PRESET_FORMAT_VERSION,
    PIPELINE_SCHEMA_VERSION,
    build_default_preset,
    validate_pipeline_preset,
)


def test_default_preset_contains_complete_configuration() -> None:
    preset = build_default_preset()

    assert preset["format_version"] == (
        PRESET_FORMAT_VERSION
    )
    assert preset["schema_version"] == (
        PIPELINE_SCHEMA_VERSION
    )
    assert preset["id"] == "default"
    assert preset["name"] == "Valeurs par défaut"
    assert preset["built_in"] is True
    assert preset["created_at"] is None

    configuration = preset["configuration"]

    assert len(configuration) == 9
    assert (
        configuration["PEAK_DETECTION"]["threshold"]
        == 100
    )
    assert configuration["IDENTIFICATION"]["weights"] == {
        "mz": 0.4,
        "ccs": 0.4,
        "rt": 0.2,
    }


def test_partial_preset_is_completed_and_normalized() -> None:
    preset, errors = validate_pipeline_preset(
        {
            "format_version": 1,
            "schema_version": 1,
            "name": "Analyse personnalisée",
            "description": "Preset de test",
            "configuration": {
                "PEAK_DETECTION": {
                    "threshold": 275,
                },
                "IDENTIFICATION": {
                    "weights.mz": 0.5,
                    "weights.ccs": 0.3,
                    "weights.rt": 0.2,
                },
            },
        }
    )

    assert errors == []
    assert preset is not None

    configuration = preset["configuration"]

    assert len(configuration) == 9
    assert (
        configuration["PEAK_DETECTION"]["threshold"]
        == 275
    )
    assert (
        configuration["PEAK_DETECTION"]
        ["smooth_iterations"]
        == 7
    )
    assert configuration["IDENTIFICATION"]["weights"] == {
        "mz": 0.5,
        "ccs": 0.3,
        "rt": 0.2,
    }
    assert preset["built_in"] is False
    assert preset["created_at"] is not None


def test_preset_rejects_incompatible_versions() -> None:
    preset, errors = validate_pipeline_preset(
        {
            "format_version": 2,
            "schema_version": 99,
            "name": "Ancien preset",
            "configuration": {},
        }
    )

    assert preset is None
    assert (
        "Version de format de preset incompatible."
        in errors
    )
    assert (
        "Version du schéma de pipeline incompatible."
        in errors
    )


def test_preset_requires_a_name() -> None:
    preset, errors = validate_pipeline_preset(
        {
            "format_version": 1,
            "schema_version": 1,
            "name": "   ",
            "configuration": {},
        }
    )

    assert preset is None
    assert (
        "Le nom du preset est obligatoire."
        in errors
    )


def test_preset_rejects_invalid_configuration() -> None:
    preset, errors = validate_pipeline_preset(
        {
            "format_version": 1,
            "schema_version": 1,
            "name": "Preset invalide",
            "configuration": {
                "INTRA_CLUSTERING": {
                    "mz_ppm": 0,
                    "algorithm": "invalid",
                },
                "IDENTIFICATION": {
                    "weights.mz": 0.5,
                    "weights.ccs": 0.5,
                    "weights.rt": 0.5,
                },
            },
        }
    )

    assert preset is None

    assert any(
        "INTRA_CLUSTERING.mz_ppm" in error
        for error in errors
    )
    assert any(
        "INTRA_CLUSTERING.algorithm" in error
        for error in errors
    )
    assert any(
        "somme des poids" in error
        for error in errors
    )


def test_preset_rejects_missing_configuration() -> None:
    preset, errors = validate_pipeline_preset(
        {
            "format_version": 1,
            "schema_version": 1,
            "name": "Preset sans configuration",
        }
    )

    assert preset is None
    assert (
        "La configuration du preset est absente "
        "ou invalide."
        in errors
    )
