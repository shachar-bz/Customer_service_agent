"""Labels the agent's answer with one OpenAI Decisions API choice call (ok or the kind of problem) and its probabilities."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from orchestration.response_validator.fast_validator_prompt import (
    FAST_VALIDATION_CHOICES,
    FAST_VALIDATION_INSTRUCTIONS,
    OK_LABEL,
)
from orchestration.response_validator.response_context import format_response_context

FAST_VALIDATOR_MODEL = "gpt-6-luna"
FAST_VALIDATION_QUESTION_NAME = "response_quality"
# The answer passes when the ok choice gets at least this probability.
OK_PROBABILITY_THRESHOLD = 0.5


class FastValidationError(Exception):
    """The Decisions API answered, but not with a usable choice (e.g. a refusal)."""


@dataclass(frozen=True)
class FastValidationResult:
    probability_by_label: dict[str, float]
    latency_ms: float

    @property
    def ok_probability(self) -> float:
        return self.probability_by_label.get(OK_LABEL, 0.0)

    @property
    def is_ok(self) -> bool:
        return self.ok_probability >= OK_PROBABILITY_THRESHOLD

    @property
    def most_likely_label(self) -> str:
        problem_labels = [label for label in self.probability_by_label if label != OK_LABEL]
        return max(problem_labels, key=self.probability_by_label.__getitem__, default=OK_LABEL)


def run_fast_validation(
    decisions_client: OpenAI, question: str, answer: str, products: list[dict[str, Any]]
) -> FastValidationResult:
    start_time = time.perf_counter()
    decision = decisions_client.decisions.create(
        model=FAST_VALIDATOR_MODEL,
        input=format_response_context(question, answer, products),
        questions=[
            {
                "type": "choice",
                "name": FAST_VALIDATION_QUESTION_NAME,
                "instructions": FAST_VALIDATION_INSTRUCTIONS,
                "choices": FAST_VALIDATION_CHOICES,
            }
        ],
    )
    choice_answer = next(
        (answer for answer in decision.answers if answer.name == FAST_VALIDATION_QUESTION_NAME),
        None,
    )
    if choice_answer is None or choice_answer.type != "choice" or not choice_answer.probabilities:
        answer_type = "no answer" if choice_answer is None else choice_answer.type
        raise FastValidationError(f"Expected a choice answer with probabilities, got {answer_type}.")
    return FastValidationResult(
        probability_by_label={
            str(choice_probability.value): choice_probability.probability
            for choice_probability in choice_answer.probabilities
        },
        latency_ms=(time.perf_counter() - start_time) * 1000,
    )
