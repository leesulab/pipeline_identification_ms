"""Tests CORS pour l'interface locale Tauri."""

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_tauri_dev_preflight_is_allowed(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_API_TOKEN",
        "secret-local-token",
    )

    response = client.options(
        "/api/v1/steps",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": (
                "authorization"
            ),
        },
    )

    assert response.status_code == 200

    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:1420"
    )

    allowed_headers = response.headers[
        "access-control-allow-headers"
    ].lower()

    assert "authorization" in allowed_headers


def test_unknown_origin_is_not_allowed(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_API_TOKEN",
        "secret-local-token",
    )

    response = client.options(
        "/api/v1/steps",
        headers={
            "Origin": "https://example.org",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": (
                "authorization"
            ),
        },
    )

    assert response.status_code == 400
    assert (
        "access-control-allow-origin"
        not in response.headers
    )
