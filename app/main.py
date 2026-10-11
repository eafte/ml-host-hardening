"""Application factory and composition root."""

from fastapi import FastAPI

from app.api.routes import router
from app.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.services.inference import InferenceService
from app.services.model import LogisticModel


def build_inference_service(settings: Settings) -> InferenceService:
    """Assemble the inference service from configuration."""
    model = LogisticModel(settings.model_weights, settings.model_bias)
    return InferenceService(model)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application.

    Settings can be injected for tests; otherwise they come from the environment.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # Interactive docs and the schema are exposed in development only:
    # in production they reveal the API's full surface to anyone who asks.
    is_dev = settings.environment == "development"
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if is_dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_dev else None,
    )
    app.state.inference_service = build_inference_service(settings)
    app.include_router(router)
    return app
