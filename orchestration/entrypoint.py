"""Public entry point: answer_question(question) -> str. Never raises; every run is logged.

Import-safe: the runtime (data, vector index, tools, OpenAI) loads on the first question.
"""
from __future__ import annotations

from orchestration.logger import log_failure, log_question_outcome

FAILURE_ANSWER = (
    "Sorry, something went wrong while answering your question. Please try again later."
)


def answer_question(question: str) -> str:
    try:
        # Imported here to keep importing this module cheap.
        from orchestration.runtime import run_customer_service_agent

        question_outcome = run_customer_service_agent(question)
    except Exception:
        log_failure(question)
        return FAILURE_ANSWER

    log_question_outcome(question_outcome)
    return question_outcome.final_answer
