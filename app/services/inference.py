"""Inference use-case: validates input against the model and scores it."""

from collections.abc import Sequence

from app.services.model import Model


class FeatureCountError(ValueError):
    """Raised when the input length does not match the model's expectation."""


class InferenceService:
    """Coordinates prediction requests against an injected model."""

    def __init__(self, model: Model) -> None:
        self._model = model

    def predict(self, features: Sequence[float]) -> float:
        """Return the model score for ``features``.

        Raises:
            FeatureCountError: if ``features`` has the wrong length.
        """
        expected = self._model.n_features
        if len(features) != expected:
            raise FeatureCountError(
                f"expected {expected} features, received {len(features)}"
            )
        return self._model.score(features)
