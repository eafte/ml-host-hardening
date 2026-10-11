"""Dependency providers injected into route handlers."""

from typing import Annotated

from fastapi import Depends, Request

from app.services.inference import InferenceService


def get_inference_service(request: Request) -> InferenceService:
    """Return the service instance assembled at application startup."""
    return request.app.state.inference_service


InferenceServiceDep = Annotated[InferenceService, Depends(get_inference_service)]
