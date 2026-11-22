"""Tests HTTP du schéma dynamique de la pipeline."""

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_pipeline_schema_endpoint() -> None:
    response = client.get(
        "/api/v1/pipeline/schema"
    )

    assert response.status_code == 200

    schema = response.json()

    assert schema["version"] == 1
    assert len(schema["sections"]) == 9

    parameter_count = sum(
        len(section["parameters"])
        for section in schema["sections"]
    )

    assert parameter_count == 56


def test_pipeline_schema_contains_defaults() -> None:
    schema = client.get(
        "/api/v1/pipeline/schema"
    ).json()

    peak_detection = next(
        section
        for section in schema["sections"]
        if section["id"] == "PEAK_DETECTION"
    )

    defaults = {
        parameter["path"]: parameter["default"]
        for parameter in peak_detection["parameters"]
    }

    assert defaults["threshold"] == 100
    assert defaults["smooth_iterations"] == 7
    assert defaults["smooth_radius.mz"] == 0
    assert defaults["peak_radius.drift_time"] == 10


def test_pipeline_schema_is_visible_in_openapi() -> None:
    openapi = client.get("/openapi.json").json()

    assert (
        "/api/v1/pipeline/schema"
        in openapi["paths"]
    )
