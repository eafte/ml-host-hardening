"""Shared test fixtures."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def make_client() -> Callable[..., TestClient]:
    """Return a factory that builds a client for a given environment."""

    def _make(environment: str = "production") -> TestClient:
        # _env_file=None isolates tests from any local .env file.
        settings = Settings(
            _env_file=None,
            model_weights=[0.8, -0.4, 1.2],
            model_bias=-0.3,
            environment=environment,
        )
        return TestClient(create_app(settings))

    return _make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """Client for the default (production) configuration."""
    return make_client()
