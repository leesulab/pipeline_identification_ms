"""Tests de l'authentification locale par jeton."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_health_remains_public(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_API_TOKEN",
        "secret-local-token",
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_route_requires_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_API_TOKEN",
        "secret-local-token",
    )
    monkeypatch.setenv(
        "PIPELINE_JOBS_DIR",
        str(tmp_path / "jobs"),
    )

    response = client.get("/api/v1/steps")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "invalide" in response.json()["detail"]


def test_api_route_rejects_wrong_token(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_API_TOKEN",
        "secret-local-token",
    )

    response = client.get(
        "/api/v1/steps",
        headers={
            "Authorization": "Bearer mauvais-token",
        },
    )

    assert response.status_code == 401


def test_api_route_accepts_valid_token(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "PIPELINE_API_TOKEN",
        "secret-local-token",
    )

    response = client.get(
        "/api/v1/steps",
        headers={
            "Authorization": (
                "Bearer secret-local-token"
            ),
        },
    )

    assert response.status_code == 200
    assert "calibration" in response.json()
    assert "categories" in response.json()


def test_authentication_is_optional_without_environment_token(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "PIPELINE_API_TOKEN",
        raising=False,
    )

    response = client.get("/api/v1/steps")

    assert response.status_code == 200
