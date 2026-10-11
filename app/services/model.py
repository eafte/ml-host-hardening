"""Model interface and a logistic-regression implementation."""

import math
from collections.abc import Sequence
from typing import Protocol


class Model(Protocol):
    """Contract that any scoring model must satisfy."""

    @property
    def n_features(self) -> int:
        """Number of input features the model expects."""
        ...

    def score(self, features: Sequence[float]) -> float:
        """Return a probability in the closed interval [0, 1]."""
        ...


def _sigmoid(z: float) -> float:
    """Numerically stable logistic function.

    A naive ``1 / (1 + exp(-z))`` raises OverflowError for large negative z,
    which an attacker could trigger with extreme inputs.
    """
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


class LogisticModel:
    """Logistic-regression scorer with fixed weights and bias."""

    def __init__(self, weights: Sequence[float], bias: float) -> None:
        self._weights = tuple(weights)
        self._bias = bias

    @property
    def n_features(self) -> int:
        return len(self._weights)

    def score(self, features: Sequence[float]) -> float:
        z = sum(w * x for w, x in zip(self._weights, features)) + self._bias
        return _sigmoid(z)
