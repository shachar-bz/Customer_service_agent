"""Debug logging for us: configures agent.log and writes each run's trace (tool calls, args, results, errors, latency, answer) or failure."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestration.agent import AgentRun

AGENT_LOG_PATH = Path(__file__).resolve().parent.parent / "agent.log"

agent_logger = logging.getLogger("customer_service_agent")


def ensure_agent_log_handler() -> None:
    if agent_logger.handlers:
        return
    file_handler = logging.FileHandler(AGENT_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s\n%(message)s\n"))
    agent_logger.addHandler(file_handler)
    agent_logger.setLevel(logging.INFO)
    agent_logger.propagate = False


def format_agent_run(agent_run: AgentRun) -> str:
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
    lines.append(f"FINAL ANSWER: {agent_run.final_answer}")
    return "\n".join(lines)


def log_agent_run(agent_run: AgentRun) -> None:
    ensure_agent_log_handler()
    agent_logger.info(format_agent_run(agent_run))


def log_failure(question: str) -> None:
    """Call from an except block: records the active exception's traceback."""
    ensure_agent_log_handler()
    agent_logger.exception("QUESTION: %s\nanswer_question failed", question)
