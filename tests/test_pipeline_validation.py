"""Tests de validation des configurations de pipeline."""

from api.pipeline_validation import (
    validate_pipeline_configuration,
)


def test_empty_configuration_uses_all_defaults() -> None:
    normalized, errors = validate_pipeline_configuration({})

    assert errors == []
    assert len(normalized) == 9

    assert (
        normalized["PEAK_DETECTION"]["threshold"]
        == 100
    )

    assert (
        normalized["PEAK_DETECTION"]["smooth_radius"]
        == {
            "mz": 0,
            "drift_time": 1,
            "retention_time": 0,
        }
    )

    assert normalized["IDENTIFICATION"]["weights"] == {
        "mz": 0.4,
        "ccs": 0.4,
        "rt": 0.2,
    }


def test_partial_configuration_overrides_defaults() -> None:
    normalized, errors = validate_pipeline_configuration(
        {
            "PEAK_DETECTION": {
                "threshold": 250,
            },
            "IDENTIFICATION": {
                "database_key": "negative",
                "weights.mz": 0.5,
                "weights.ccs": 0.3,
                "weights.rt": 0.2,
            },
        }
    )

    assert errors == []

    assert (
        normalized["PEAK_DETECTION"]["threshold"]
        == 250
    )

    assert (
        normalized["PEAK_DETECTION"]["smooth_iterations"]
        == 7
    )

    assert (
        normalized["IDENTIFICATION"]["database_key"]
        == "negative"
    )

    assert normalized["IDENTIFICATION"]["weights"] == {
        "mz": 0.5,
        "ccs": 0.3,
        "rt": 0.2,
    }


def test_invalid_types_are_rejected() -> None:
    _, errors = validate_pipeline_configuration(
        {
            "PROCESSING": {
                "parallel_max_workers": 2.5,
            },
            "PEAK_DETECTION": {
                "threshold": True,
            },
        }
    )

    assert any(
        "PROCESSING.parallel_max_workers"
        in error
        and "integer attendu"
        in error
        for error in errors
    )

    assert any(
        "PEAK_DETECTION.threshold"
        in error
        and "integer attendu"
        in error
        for error in errors
    )


def test_numeric_bounds_are_checked() -> None:
    _, errors = validate_pipeline_configuration(
        {
            "INTRA_CLUSTERING": {
                "mz_ppm": 0.0,
                "dbscan_min_samples": 0,
            },
            "IDENTIFICATION": {
                "ms2_score_threshold": 1.5,
            },
        }
    )

    assert any(
        "INTRA_CLUSTERING.mz_ppm"
        in error
        and "valeur minimale 0.01"
        in error
        for error in errors
    )

    assert any(
        "INTRA_CLUSTERING.dbscan_min_samples"
        in error
        and "valeur minimale 1"
        in error
        for error in errors
    )

    assert any(
        "IDENTIFICATION.ms2_score_threshold"
        in error
        and "valeur maximale 1.0"
        in error
        for error in errors
    )


def test_choice_lists_are_checked() -> None:
    _, errors = validate_pipeline_configuration(
        {
            "INTRA_CLUSTERING": {
                "algorithm": "invalid_tree",
            },
            "IDENTIFICATION": {
                "database_key": "neutral",
            },
        }
    )

    assert any(
        "INTRA_CLUSTERING.algorithm"
        in error
        and "valeur non autorisée"
        in error
        for error in errors
    )

    assert any(
        "IDENTIFICATION.database_key"
        in error
        and "valeur non autorisée"
        in error
        for error in errors
    )


def test_identification_weights_must_sum_to_one() -> None:
    _, errors = validate_pipeline_configuration(
        {
            "IDENTIFICATION": {
                "weights.mz": 0.5,
                "weights.ccs": 0.5,
                "weights.rt": 0.5,
            },
        }
    )

    assert any(
        "la somme des poids doit être égale à 1"
        in error
        for error in errors
    )


def test_unknown_sections_and_parameters_are_rejected() -> None:
    _, errors = validate_pipeline_configuration(
        {
            "UNKNOWN_SECTION": {
                "value": 1,
            },
            "PROCESSING": {
                "unknown_parameter": 42,
            },
        }
    )

    assert (
        "Section inconnue : UNKNOWN_SECTION."
        in errors
    )

    assert (
        "PROCESSING.unknown_parameter : "
        "paramètre inconnu."
        in errors
    )


def test_normalized_nested_configuration_is_accepted() -> None:
    first_normalized, first_errors = (
        validate_pipeline_configuration(
            {
                "PEAK_DETECTION": {
                    "threshold": 275,
                },
                "IDENTIFICATION": {
                    "weights.mz": 0.5,
                    "weights.ccs": 0.3,
                    "weights.rt": 0.2,
                },
            }
        )
    )

    assert first_errors == []

    second_normalized, second_errors = (
        validate_pipeline_configuration(
            first_normalized
        )
    )

    assert second_errors == []
    assert second_normalized == first_normalized

    assert (
        second_normalized["PEAK_DETECTION"]
        ["smooth_radius"]
        == {
            "mz": 0,
            "drift_time": 1,
            "retention_time": 0,
        }
    )

    assert (
        second_normalized["IDENTIFICATION"]
        ["tolerances"]
        == {
            "mz_ppm": 5.0,
            "ccs_percent": 8.0,
            "rt_min": 0.1,
        }
    )

    assert (
        second_normalized["IDENTIFICATION"]
        ["weights"]
        == {
            "mz": 0.5,
            "ccs": 0.3,
            "rt": 0.2,
        }
    )
