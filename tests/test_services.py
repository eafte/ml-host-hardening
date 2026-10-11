"""Unit tests for the service layer, independent of HTTP."""

from collections.abc import Sequence

import pytest

from app.services.inference import FeatureCountError, InferenceService
from app.services.model import LogisticModel


@pytest.fixture
def service() -> InferenceService:
    return InferenceService(LogisticModel([0.8, -0.4, 1.2], -0.3))


def test_known_input_gives_expected_score(service: InferenceService) -> None:
    assert service.predict([1.0, 2.0, 3.0]) == pytest.approx(0.9644, abs=1e-4)


@pytest.mark.parametrize("extreme", [1e6, -1e6])
def test_extreme_inputs_stay_in_range(
    service: InferenceService, extreme: float
) -> None:
    assert 0.0 <= service.predict([extreme, 0.0, 0.0]) <= 1.0


def test_wrong_feature_count_raises(service: InferenceService) -> None:
    with pytest.raises(FeatureCountError):
        service.predict([1.0])


def test_service_accepts_any_model_implementation() -> None:
    class ConstantModel:
        n_features = 2

        def score(self, features: Sequence[float]) -> float:
            return 0.5

    assert InferenceService(ConstantModel()).predict([1.0, 2.0]) == 0.5
