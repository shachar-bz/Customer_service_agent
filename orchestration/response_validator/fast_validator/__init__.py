"""Fast validation: one Decisions API choice call that labels the agent's answer."""
from orchestration.response_validator.fast_validator.fast_validator import (
    OK_PROBABILITY_THRESHOLD,
    FastValidationError,
    FastValidationResult,
    FastValidator,
)
from orchestration.response_validator.fast_validator.prompt import OK_LABEL

__all__ = [
    "OK_LABEL",
    "OK_PROBABILITY_THRESHOLD",
    "FastValidationError",
    "FastValidationResult",
    "FastValidator",
]
