"""Customer-service agent loop: Responses API tool-calling with LLM/TOOL caps. Returns an AgentRun; knows nothing about logging or wiring."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from orchestration.prompt import SYSTEM_PROMPT

if TYPE_CHECKING:
    from openai import OpenAI

    from orchestration.tool_registry import ToolRegistry

AGENT_MODEL = "gpt-6.1-sol"
REASONING_EFFORT = "medium"
# Max model calls per question, including the final forced-answer call.
LLM_CAP = 8
# Max tool executions per question; one model call can request several tools.
TOOL_CAP = 12

CAP_REACHED_APOLOGY = (
    "Sorry, I could not gather enough information to answer your question. Please try "
    "rephrasing it or asking a more specific question."
)
TOOL_BUDGET_EXHAUSTED_MESSAGE = "Tool budget exhausted: this tool was not run."
FORCED_ANSWER_INSTRUCTION = (
    "You cannot call any more tools. If the tool results above are enough to answer the "
    "customer's question, answer it now. Otherwise reply with exactly this text:\n"
    f"{CAP_REACHED_APOLOGY}"
)


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


def _elapsed_ms(start_time: float) -> float:
    return (time.perf_counter() - start_time) * 1000


def _function_call_output(call_id: str, tool_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(tool_result, ensure_ascii=False),
    }


def _run_tool_call(registry: ToolRegistry, function_call: Any, agent_run: AgentRun) -> dict[str, Any]:
    if len(agent_run.tool_calls) >= TOOL_CAP:
        tool_result = {"error": TOOL_BUDGET_EXHAUSTED_MESSAGE}
        latency_ms = 0.0
    else:
        start_time = time.perf_counter()
        tool_result = registry.dispatch(function_call.name, function_call.arguments)
        latency_ms = _elapsed_ms(start_time)
    agent_run.tool_calls.append(
        ToolCallRecord(
            tool_name=function_call.name,
            raw_arguments_json=function_call.arguments,
            result=tool_result,
            error=tool_result.get("error"),
            latency_ms=latency_ms,
        )
    )
    return tool_result


def run_agent(question: str, registry: ToolRegistry, agent_client: OpenAI) -> AgentRun:
    """One question, one answer: no conversation history beyond this call."""
    start_time = time.perf_counter()
    agent_run = AgentRun(question=question)
    # Kept locally (store=False): every turn resends the full transcript.
    input_items: list[Any] = [{"role": "user", "content": question}]

    def call_model(tool_choice: str) -> Any:
        agent_run.llm_call_count += 1
        response = agent_client.responses.create(
            model=AGENT_MODEL,
            instructions=SYSTEM_PROMPT,
            input=input_items,
            tools=registry.tool_schemas,
            tool_choice=tool_choice,
            parallel_tool_calls=True,
            reasoning={"effort": REASONING_EFFORT},
            store=False,
            # Reasoning items must travel back to the model since nothing is stored server-side.
            include=["reasoning.encrypted_content"],
        )
        input_items.extend(response.output)
        return response

    # The last of the LLM_CAP calls is reserved for the forced answer.
    for _ in range(LLM_CAP - 1):
        response = call_model(tool_choice="auto")
        function_calls = [item for item in response.output if item.type == "function_call"]
        if not function_calls:
            agent_run.final_answer = response.output_text or CAP_REACHED_APOLOGY
            agent_run.total_latency_ms = _elapsed_ms(start_time)
            return agent_run

        for function_call in function_calls:
            tool_result = _run_tool_call(registry, function_call, agent_run)
            input_items.append(_function_call_output(function_call.call_id, tool_result))
        if len(agent_run.tool_calls) >= TOOL_CAP:
            break

    agent_run.stopped_by_cap = True
    input_items.append({"role": "developer", "content": FORCED_ANSWER_INSTRUCTION})
    response = call_model(tool_choice="none")
    agent_run.final_answer = response.output_text or CAP_REACHED_APOLOGY
    agent_run.total_latency_ms = _elapsed_ms(start_time)
    return agent_run
