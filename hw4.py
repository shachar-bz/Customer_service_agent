"""Assignment entry point: answer_question(question) runs the customer-service agent on one question.

Import-safe: data, vector index and clients load lazily on the first call. Every run's trace
(tool calls, arguments, results, errors, latency, final answer) is logged to agent.log.
"""
from __future__ import annotations

import logging
from pathlib import Path

AGENT_LOG_PATH = Path(__file__).resolve().parent / "agent.log"
FAILURE_ANSWER = (
    "Sorry, something went wrong while answering your question. Please try again later."
)

agent_logger = logging.getLogger("customer_service_agent")


def _ensure_agent_log_handler() -> None:
    if agent_logger.handlers:
        return
    file_handler = logging.FileHandler(AGENT_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s\n%(message)s\n"))
    agent_logger.addHandler(file_handler)
    agent_logger.setLevel(logging.INFO)
    agent_logger.propagate = False


def answer_question(question: str) -> str:
    """Never raises: any failure is logged and answered with FAILURE_ANSWER."""
    _ensure_agent_log_handler()
    try:
        # Imported here so `import hw4` stays cheap (chromadb, tools, OpenAI clients).
        from orchestration.agent_trace import format_agent_run
        from orchestration.runtime import run_customer_service_agent

        agent_run = run_customer_service_agent(question)
    except Exception:
        agent_logger.exception("QUESTION: %s\nanswer_question failed", question)
        return FAILURE_ANSWER

    agent_logger.info(format_agent_run(agent_run))
    return agent_run.final_answer


if __name__ == "__main__":
    import sys

    print(answer_question(" ".join(sys.argv[1:]) or input("Question: ")))
