"""Public entry point: answer_question(question) -> str. Never raises; every run is logged.

Import-safe: the runtime (data, vector index, tools, OpenAI) loads on the first question.
"""
from __future__ import annotations

from orchestration.logger import log_agent_run, log_failure

FAILURE_ANSWER = (
    "Sorry, something went wrong while answering your question. Please try again later."
)


def answer_question(question: str) -> str:
    try:
        # Imported here to keep importing this module cheap.
        from orchestration.runtime import run_customer_service_agent

        agent_run = run_customer_service_agent(question)
    except Exception:
        log_failure(question)
        return FAILURE_ANSWER

    log_agent_run(agent_run)
    return agent_run.final_answer
