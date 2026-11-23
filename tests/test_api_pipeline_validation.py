"""Tests HTTP de validation des configurations."""

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_empty_configuration_returns_defaults() -> None:
    response = client.post(
        "/api/v1/pipeline/configuration/validate",
        json={
            "configuration": {},
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["valid"] is True
    assert result["errors"] == []

    assert (
        result["configuration"]
        ["PEAK_DETECTION"]
        ["threshold"]
        == 100
    )

    assert (
        result["configuration"]
        ["IDENTIFICATION"]
        ["weights"]
        == {
            "mz": 0.4,
            "ccs": 0.4,
            "rt": 0.2,
        }
    )


def test_partial_configuration_is_normalized() -> None:
    response = client.post(
        "/api/v1/pipeline/configuration/validate",
        json={
            "configuration": {
                "PEAK_DETECTION": {
                    "threshold": 350,
                },
                "IDENTIFICATION": {
                    "database_key": "negative",
                },
            },
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["valid"] is True

    assert (
        result["configuration"]
        ["PEAK_DETECTION"]
        ["threshold"]
        == 350
    )

    assert (
        result["configuration"]
        ["PEAK_DETECTION"]
        ["smooth_iterations"]
        == 7
    )

    assert (
        result["configuration"]
        ["IDENTIFICATION"]
        ["database_key"]
        == "negative"
    )


def test_invalid_configuration_returns_errors() -> None:
    response = client.post(
        "/api/v1/pipeline/configuration/validate",
        json={
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
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["valid"] is False

    assert any(
        "INTRA_CLUSTERING.mz_ppm"
        in error
        for error in result["errors"]
    )

    assert any(
        "INTRA_CLUSTERING.algorithm"
        in error
        for error in result["errors"]
    )

    assert any(
        "somme des poids"
        in error
        for error in result["errors"]
    )


def test_validation_route_is_visible_in_openapi() -> None:
    openapi = client.get("/openapi.json").json()

    assert (
        "/api/v1/pipeline/configuration/validate"
        in openapi["paths"]
    )


def test_job_creation_persists_normalized_configuration(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.post(
        "/api/v1/jobs",
        json={
            "steps": ["file_discovery"],
            "parameters": {
                "project": "Configuration test",
                "pipeline_configuration": {
                    "PEAK_DETECTION": {
                        "threshold": 275,
                    },
                    "IDENTIFICATION": {
                        "weights.mz": 0.5,
                        "weights.ccs": 0.3,
                        "weights.rt": 0.2,
                    },
                },
            },
        },
    )

    assert response.status_code == 201

    parameters = response.json()["parameters"]
    configuration = parameters[
        "pipeline_configuration"
    ]

    assert parameters["project"] == "Configuration test"

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


def test_job_creation_rejects_invalid_configuration(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.post(
        "/api/v1/jobs",
        json={
            "steps": ["file_discovery"],
            "parameters": {
                "pipeline_configuration": {
                    "INTRA_CLUSTERING": {
                        "mz_ppm": 0,
                    },
                },
            },
        },
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["message"] == (
        "La configuration de la pipeline est invalide."
    )

    assert any(
        "INTRA_CLUSTERING.mz_ppm" in error
        for error in detail["errors"]
    )
