"""Debug logging for us: configures agent.log and writes each run's trace (tool calls, args, results, errors, latency, response validation, answer) or failure."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestration.question_outcome import QuestionOutcome

AGENT_LOG_PATH = Path(__file__).resolve().parent.parent / "agent.log"

agent_logger = logging.getLogger("customer_service_agent")


def ensure_agent_log_handler() -> None:
    if agent_logger.handlers:
        return
    file_handler = logging.FileHandler(AGENT_LOG_PATH, encoding="utf-8", delay=True)  # delay: an unwritable log never raises
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s\n%(message)s\n"))
    agent_logger.addHandler(file_handler)
    agent_logger.setLevel(logging.INFO)
    agent_logger.propagate = False


def format_question_outcome(question_outcome: QuestionOutcome) -> str:
    agent_run = question_outcome.agent_run
    lines = [
        f"QUESTION: {agent_run.question}",
        (
            f"llm_calls={agent_run.llm_call_count} tool_calls={len(agent_run.tool_calls)} "
            f"stopped_by_cap={agent_run.stopped_by_cap} total={agent_run.total_latency_ms:.0f}ms"
        ),
    ]
    for call_number, tool_call in enumerate(agent_run.tool_calls, start=1):
        lines.append(
            f"  [{call_number}] {tool_call.tool_name}({tool_call.raw_arguments_json}) "
            f"{tool_call.latency_ms:.0f}ms"
        )
        if tool_call.error is not None:
            lines.append(f"      ERROR: {tool_call.error}")
        lines.append(f"      RESULT: {json.dumps(tool_call.result, ensure_ascii=False)}")
    lines.extend(format_response_validation(question_outcome))
    lines.append(f"FINAL ANSWER: {question_outcome.final_answer}")
    return "\n".join(lines)


def format_response_validation(question_outcome: QuestionOutcome) -> list[str]:
    response_validation = question_outcome.response_validation
    lines = ["RESPONSE VALIDATION:"]
    if response_validation.skipped_reason is not None:
        lines.append(f"  skipped: {response_validation.skipped_reason}")
    fast_validation = response_validation.fast_validation
    if fast_validation is not None:
        lines.append(
            f"  fast: ok={fast_validation.is_ok} label={fast_validation.most_likely_label} "
            f"probabilities={json.dumps(fast_validation.probability_by_label)} "
            f"{fast_validation.latency_ms:.0f}ms"
        )
    review = response_validation.review
    if review is not None:
        lines.append(
            f"  review: actually_wrong={review.verdict.is_actually_wrong} "
            f"problems={json.dumps(review.verdict.problems, ensure_ascii=False)} {review.latency_ms:.0f}ms"
        )
        if review.verdict.fix_instructions:
            lines.append(f"  fix_instructions: {review.verdict.fix_instructions}")
    if response_validation.original_answer is not None:
        lines.append(f"  repaired; ORIGINAL ANSWER: {response_validation.original_answer}")
    if response_validation.error is not None:
        lines.append(f"  ERROR (answer kept): {response_validation.error}")
    return lines


def log_question_outcome(question_outcome: QuestionOutcome) -> None:
    ensure_agent_log_handler()
    agent_logger.info(format_question_outcome(question_outcome))


def log_failure(question: str) -> None:
    """Call from an except block: records the active exception's traceback."""
    ensure_agent_log_handler()
    agent_logger.exception("QUESTION: %s\nanswer_question failed", question)
