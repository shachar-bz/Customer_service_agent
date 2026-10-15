"""Debug trace of one agent run: every tool call (args, result, error, latency) and the final answer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ToolCallRecord:
    tool_name: str
    raw_arguments_json: str
    result: dict[str, Any]
    error: Optional[str]
    latency_ms: float


@dataclass
class AgentRun:
    question: str
    final_answer: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    llm_call_count: int = 0
    # True when LLM_CAP or TOOL_CAP forced the final answer.
    stopped_by_cap: bool = False
    total_latency_ms: float = 0.0


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
