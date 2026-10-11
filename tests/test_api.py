"""HTTP-level tests for the inference API."""

import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_returns_expected_score(client: TestClient) -> None:
    response = client.post("/predict", json={"features": [1.0, 2.0, 3.0]})
    assert response.status_code == 200
    assert response.json()["score"] == pytest.approx(0.9644, abs=1e-4)


@pytest.mark.parametrize(
    "payload",
    [
        {"features": []},
        {"features": [1.0]},
        {"features": [1.0, 2.0, 3.0], "admin": True},
        {"features": ["a", "b", "c"]},
        {},
        {"features": [0.0] * 65},
    ],
    ids=["empty", "wrong-length", "extra-field", "wrong-type", "missing", "oversized"],
)
def test_predict_rejects_invalid_payload(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


def test_docs_hidden_in_production(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404


def test_openapi_schema_hidden_in_production(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 404


def test_docs_available_in_development(make_client) -> None:
    assert make_client("development").get("/docs").status_code == 200
