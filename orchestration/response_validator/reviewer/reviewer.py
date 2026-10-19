"""Reviews an answer the fast validator flagged: one gpt-6-luna Responses API call, no tools, returning a structured verdict."""
from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI
from pydantic import ValidationError

from orchestration.response_validator.reviewer.prompt import REVIEWER_INSTRUCTIONS, format_reviewer_input
from orchestration.response_validator.reviewer.response_format import (
    RESPONSE_REVIEW_TEXT_FORMAT,
    ResponseReviewVerdict,
)

REVIEWER_MODEL = "gpt-6-luna"


class ResponseReviewError(Exception):
    """The reviewer answered, but not with a valid verdict (e.g. a refusal or malformed JSON)."""


@dataclass(frozen=True)
class ResponseReview:
    verdict: ResponseReviewVerdict
    latency_ms: float

    @property
    def review_feedback(self) -> str:
        """The text the repair pass hands to the agent."""
        problem_lines = "\n".join(f"- {problem}" for problem in self.verdict.problems)
        return f"{problem_lines}\nHow to fix: {self.verdict.fix_instructions}"


class ResponseReviewer:
    def __init__(self, reviewer_client: OpenAI) -> None:
        self._reviewer_client = reviewer_client

    def review(
        self, response_context: str, flagged_label: str, probability_by_label: dict[str, float]
    ) -> ResponseReview:
        start_time = time.perf_counter()
        response = self._reviewer_client.responses.create(
            model=REVIEWER_MODEL,
            instructions=REVIEWER_INSTRUCTIONS,
            input=format_reviewer_input(response_context, flagged_label, probability_by_label),
            text={"format": RESPONSE_REVIEW_TEXT_FORMAT},
            store=False,
        )
        try:
            verdict = ResponseReviewVerdict.model_validate_json(response.output_text or "")
        except ValidationError as validation_error:
            raise ResponseReviewError(f"Reviewer returned no valid verdict: {validation_error}") from validation_error
        return ResponseReview(verdict=verdict, latency_ms=(time.perf_counter() - start_time) * 1000)
