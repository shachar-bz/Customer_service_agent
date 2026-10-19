"""Reviews an answer the fast validator flagged: one gpt-6-luna Responses API call, no tools, returning a structured verdict (parsed into ResponseReviewVerdict)."""
from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI
from pydantic import BaseModel

from orchestration.response_validator.reviewer_prompt import REVIEWER_INSTRUCTIONS, format_reviewer_input

REVIEWER_MODEL = "gpt-6-luna"


class ResponseReviewVerdict(BaseModel):
    is_actually_wrong: bool
    problems: list[str]
    fix_instructions: str


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


def review_response(
    reviewer_client: OpenAI,
    question: str,
    answer: str,
    flagged_label: str,
    probability_by_label: dict[str, float],
) -> ResponseReview:
    start_time = time.perf_counter()
    response = reviewer_client.responses.parse(
        model=REVIEWER_MODEL,
        instructions=REVIEWER_INSTRUCTIONS,
        input=format_reviewer_input(question, answer, flagged_label, probability_by_label),
        text_format=ResponseReviewVerdict,
        store=False,
    )
    verdict = response.output_parsed
    if verdict is None:
        raise ResponseReviewError("Reviewer returned no parsed verdict (e.g. a refusal).")
    return ResponseReview(verdict=verdict, latency_ms=(time.perf_counter() - start_time) * 1000)
