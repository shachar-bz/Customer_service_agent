"""Response validation pipeline: fast validation, then review when doubtful, then at most one repair pass. Fails open: on any error the agent's answer stands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from orchestration.agent import AgentRun
from orchestration.response_validator.fast_validator import FastValidationResult, FastValidator
from orchestration.response_validator.response_context import (
    collect_retrieved_products,
    format_response_context,
)
from orchestration.response_validator.reviewer import ResponseReview, ResponseReviewer

SKIPPED_STOPPED_BY_CAP = "stopped_by_cap: no budget left to repair"


@dataclass
class ResponseValidation:
    skipped_reason: Optional[str] = None
    fast_validation: Optional[FastValidationResult] = None
    review: Optional[ResponseReview] = None
    # The agent's first answer, kept only when a repair pass replaced it.
    original_answer: Optional[str] = None
    # A failed step's error; the answer at that point was kept.
    error: Optional[str] = None


class ResponseValidationPipeline:
    def __init__(self, fast_validator: FastValidator, response_reviewer: ResponseReviewer) -> None:
        self._fast_validator = fast_validator
        self._response_reviewer = response_reviewer

    def validate(self, agent_run: AgentRun, repair_answer: Callable[[str], None]) -> None:
        """Records a ResponseValidation on agent_run; may replace agent_run.final_answer. Never raises.
        repair_answer(review_feedback) must resume the agent and overwrite final_answer."""
        response_validation = ResponseValidation()
        agent_run.response_validation = response_validation
        if agent_run.stopped_by_cap:
            response_validation.skipped_reason = SKIPPED_STOPPED_BY_CAP
            return

        original_answer = agent_run.final_answer
        try:
            products = collect_retrieved_products(agent_run.tool_calls)
            fast_validation = self._fast_validator.validate(agent_run.question, original_answer, products)
            response_validation.fast_validation = fast_validation
            if fast_validation.is_ok:
                return

            review = self._response_reviewer.review(
                format_response_context(agent_run.question, original_answer, products),
                fast_validation.most_likely_label,
                fast_validation.probability_by_label,
            )
            response_validation.review = review
            if not review.verdict.is_actually_wrong:
                return

            repair_answer(review.review_feedback)
            response_validation.original_answer = original_answer
        except Exception as error:
            agent_run.final_answer = original_answer
            response_validation.error = f"{type(error).__name__}: {error}"
