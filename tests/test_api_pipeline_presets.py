"""Tests HTTP des presets de configuration."""

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_list_presets_returns_default_preset() -> None:
    response = client.get(
        "/api/v1/pipeline/presets"
    )

    assert response.status_code == 200

    presets = response.json()

    assert len(presets) == 1

    default_preset = presets[0]

    assert default_preset["id"] == "default"
    assert default_preset["name"] == "Valeurs par défaut"
    assert default_preset["built_in"] is True
    assert default_preset["format_version"] == 1
    assert default_preset["schema_version"] == 1

    configuration = default_preset["configuration"]

    assert len(configuration) == 9
    assert (
        configuration["PEAK_DETECTION"]["threshold"]
        == 100
    )


def test_validate_imported_preset() -> None:
    response = client.post(
        "/api/v1/pipeline/presets/validate",
        json={
            "preset": {
                "format_version": 1,
                "schema_version": 1,
                "name": "Analyse personnalisée",
                "description": "Preset importé",
                "configuration": {
                    "PEAK_DETECTION": {
                        "threshold": 275,
                    },
                },
            },
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["valid"] is True
    assert result["errors"] == []

    preset = result["preset"]

    assert preset["name"] == "Analyse personnalisée"
    assert preset["built_in"] is False

    assert (
        preset["configuration"]
        ["PEAK_DETECTION"]
        ["threshold"]
        == 275
    )

    assert len(preset["configuration"]) == 9


def test_invalid_preset_returns_all_errors() -> None:
    response = client.post(
        "/api/v1/pipeline/presets/validate",
        json={
            "preset": {
                "format_version": 99,
                "schema_version": 1,
                "name": "",
                "configuration": {
                    "INTRA_CLUSTERING": {
                        "mz_ppm": 0,
                    },
                },
            },
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["valid"] is False
    assert result["preset"] is None

    assert (
        "Version de format de preset incompatible."
        in result["errors"]
    )

    assert (
        "Le nom du preset est obligatoire."
        in result["errors"]
    )

    assert any(
        "INTRA_CLUSTERING.mz_ppm" in error
        for error in result["errors"]
    )


def test_preset_routes_are_visible_in_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/pipeline/presets" in paths

    assert (
        "/api/v1/pipeline/presets/validate"
        in paths
    )
