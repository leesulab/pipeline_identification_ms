"""Tests du schéma de configuration dynamique."""

from api.pipeline_schema import build_pipeline_schema


def test_pipeline_schema_contains_nine_sections() -> None:
    schema = build_pipeline_schema()

    assert schema["version"] == 1
    assert len(schema["sections"]) == 9


def test_pipeline_schema_flattens_nested_parameters() -> None:
    schema = build_pipeline_schema()

    parameter_paths = {
        parameter["path"]
        for section in schema["sections"]
        for parameter in section["parameters"]
    }

    assert "threshold" in parameter_paths
    assert "smooth_radius.mz" in parameter_paths
    assert "peak_radius.drift_time" in parameter_paths
    assert "tolerances.ccs_percent" in parameter_paths
    assert "weights.rt" in parameter_paths


def test_pipeline_schema_contains_56_editable_values() -> None:
    schema = build_pipeline_schema()

    parameter_count = sum(
        len(section["parameters"])
        for section in schema["sections"]
    )

    assert parameter_count == 56


def test_pipeline_schema_preserves_defaults() -> None:
    schema = build_pipeline_schema()

    identification = next(
        section
        for section in schema["sections"]
        if section["id"] == "IDENTIFICATION"
    )

    defaults = {
        parameter["path"]: parameter["default"]
        for parameter in identification["parameters"]
    }

    assert defaults["database_key"] == "positive"
    assert defaults["tolerances.mz_ppm"] == 5
    assert defaults["weights.mz"] == 0.4
    assert defaults["ms2_score_threshold"] == 0.2
