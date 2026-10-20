"""Response validation pipeline: fast validation, then review when doubtful, then at most one repair pass. Fails open: on any error the agent's answer stands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from orchestration.main_agent.agent import AgentRun
from orchestration.response_validator.fast_validator import FastValidationResult
from orchestration.response_validator.response_context import (
    collect_customer_interests,
    collect_recommended_products,
    collect_retrieved_products,
)
from orchestration.response_validator.reviewer import ResponseReview

# (question, answer, recommended products, customer interests) -> fast validation; e.g. run_fast_validation with its client bound.
FastValidate = Callable[[str, str, list[dict[str, Any]], list[str]], FastValidationResult]
# (question, answer, flagged label, probabilities, customer interests, retrieved products) -> review;
# e.g. review_response with its client bound.
ReviewResponse = Callable[[str, str, str, dict[str, float], list[str], list[dict[str, Any]]], ResponseReview]


@dataclass
class ResponseValidation:
    # The answer the customer gets: the agent's answer, or the repaired one.
    final_answer: str
    fast_validation: Optional[FastValidationResult] = None
    review: Optional[ResponseReview] = None
    # The agent's first answer, kept only when a repair pass replaced it.
    original_answer: Optional[str] = None
    # A failed step's error; the answer at that point was kept.
    error: Optional[str] = None


def validate_response(
    agent_run: AgentRun,
    fast_validate: FastValidate,
    review_response: ReviewResponse,
    repair_answer: Callable[[str], str],
) -> ResponseValidation:
    """Returns what validation found, including the answer the customer should get. Never raises.
    agent_run is read-only input. repair_answer(review_feedback) resumes the agent and returns
    the repaired answer; if anything fails, final_answer stays the agent's original answer."""
    original_answer = agent_run.final_answer
    response_validation = ResponseValidation(final_answer=original_answer)
    # A capped run is not validated: no budget is left to repair it.
    if agent_run.stopped_by_cap:
        return response_validation

    try:
        customer_interests = collect_customer_interests(agent_run.tool_calls)
        products = collect_recommended_products(agent_run.tool_calls, original_answer)
        fast_validation = fast_validate(agent_run.question, original_answer, products, customer_interests)
        response_validation.fast_validation = fast_validation
        if fast_validation.is_ok:
            return response_validation

        review = review_response(
            agent_run.question,
            original_answer,
            fast_validation.most_likely_label,
            fast_validation.probability_by_label,
            customer_interests,
            collect_retrieved_products(agent_run.tool_calls),
        )
        response_validation.review = review
        if not review.verdict.is_actually_wrong:
            return response_validation

        response_validation.final_answer = repair_answer(review.review_feedback)
        response_validation.original_answer = original_answer
    except Exception as error:
        response_validation.error = f"{type(error).__name__}: {error}"
    return response_validation
