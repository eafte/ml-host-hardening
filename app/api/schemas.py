"""Request and response schemas for the inference API."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Upper bound on input size: caps per-request memory and CPU use.
MAX_FEATURES = 64

# NaN and infinity are rejected: they poison arithmetic and can crash scoring.
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class PredictionRequest(BaseModel):
    """Input payload for a single prediction."""

    # Unknown fields are rejected so clients cannot smuggle in unvalidated data.
    model_config = ConfigDict(extra="forbid")

    features: list[FiniteFloat] = Field(min_length=1, max_length=MAX_FEATURES)


class PredictionResponse(BaseModel):
    """Output payload for a single prediction."""

    score: float = Field(ge=0.0, le=1.0)
