"""HTTP routes for the inference API."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import InferenceServiceDep
from app.api.schemas import PredictionRequest, PredictionResponse
from app.services.inference import FeatureCountError

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Returns no version or host details."""
    return {"status": "ok"}


@router.post("/predict", response_model=PredictionResponse)
def predict(
    payload: PredictionRequest, service: InferenceServiceDep
) -> PredictionResponse:
    """Score a single feature vector."""
    try:
        score = service.predict(payload.features)
    except FeatureCountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return PredictionResponse(score=score)
