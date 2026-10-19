import json
from types import SimpleNamespace

from orchestration.agent import (
    CAP_REACHED_APOLOGY,
    LLM_CAP,
    TOOL_BUDGET_EXHAUSTED_MESSAGE,
    TOOL_CAP,
    repair_agent_answer,
    run_agent,
)
from orchestration.tool_registry import RegisteredTool, ToolRegistry
from tools.calculator import CALCULATOR_SCHEMA, CalculatorArgs, calculator

ADD_ARGUMENTS = json.dumps({"expression": "1 + 1"})


def function_call(call_id, name="calculator", arguments=ADD_ARGUMENTS):
    return SimpleNamespace(type="function_call", name=name, arguments=arguments, call_id=call_id)


def tool_response(*function_calls):
    return SimpleNamespace(output=list(function_calls), output_text="")


def answer_response(text):
    return SimpleNamespace(output=[SimpleNamespace(type="message")], output_text=text)


class FakeAgentClient:
    """Replays scripted responses; once the script runs out, keeps requesting a tool call."""

    def __init__(self, scripted_responses, forced_answer="forced answer"):
        self._scripted_responses = list(scripted_responses)
        self._forced_answer = forced_answer
        self.requests = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.requests.append({**request, "input": list(request["input"])})
        if request["tool_choice"] == "none":
            return answer_response(self._forced_answer)
        if self._scripted_responses:
            return self._scripted_responses.pop(0)
        return tool_response(function_call(f"call_{len(self.requests)}"))


def calculator_registry():
    return ToolRegistry([RegisteredTool(CALCULATOR_SCHEMA, CalculatorArgs, calculator)])


def test_answers_directly_without_tools():
    agent_client = FakeAgentClient([answer_response("Hello!")])

    agent_run = run_agent("hi", calculator_registry(), agent_client)

    assert agent_run.final_answer == "Hello!"
    assert agent_run.llm_call_count == 1
    assert agent_run.tool_calls == []
    assert not agent_run.stopped_by_cap


def test_runs_tool_and_feeds_result_back():
    agent_client = FakeAgentClient([tool_response(function_call("call_a")), answer_response("2")])

    agent_run = run_agent("1+1?", calculator_registry(), agent_client)

    assert agent_run.final_answer == "2"
    [tool_call] = agent_run.tool_calls
    assert tool_call.tool_name == "calculator"
    assert tool_call.result == {"result": 2}
    assert tool_call.error is None
    tool_output = agent_client.requests[1]["input"][-1]
    assert tool_output["type"] == "function_call_output"
    assert tool_output["call_id"] == "call_a"
    assert json.loads(tool_output["output"]) == {"result": 2}


def test_parallel_calls_each_get_an_output_in_order():
    agent_client = FakeAgentClient(
        [tool_response(function_call("call_a"), function_call("call_b")), answer_response("done")]
    )

    agent_run = run_agent("q", calculator_registry(), agent_client)

    assert len(agent_run.tool_calls) == 2
    outputs = [item for item in agent_client.requests[1]["input"] if isinstance(item, dict)]
    assert [item.get("call_id") for item in outputs[-2:]] == ["call_a", "call_b"]


def test_tool_error_is_recorded_and_sent_to_model():
    agent_client = FakeAgentClient(
        [tool_response(function_call("call_a", name="no_such_tool")), answer_response("sorry")]
    )

    agent_run = run_agent("q", calculator_registry(), agent_client)

    assert "Unknown tool" in agent_run.tool_calls[0].error


def test_llm_cap_forces_final_answer():
    agent_client = FakeAgentClient([], forced_answer="best effort")

    agent_run = run_agent("q", calculator_registry(), agent_client)

    assert agent_run.llm_call_count == LLM_CAP
    assert agent_run.stopped_by_cap
    assert agent_run.final_answer == "best effort"
    assert agent_client.requests[-1]["tool_choice"] == "none"


def test_tool_cap_blocks_extra_calls_then_forces_answer():
    too_many_calls = [function_call(f"call_{index}") for index in range(TOOL_CAP + 2)]
    agent_client = FakeAgentClient([tool_response(*too_many_calls)])

    agent_run = run_agent("q", calculator_registry(), agent_client)

    executed = [call for call in agent_run.tool_calls if call.error is None]
    blocked = [call for call in agent_run.tool_calls if call.error == TOOL_BUDGET_EXHAUSTED_MESSAGE]
    assert len(executed) == TOOL_CAP
    assert len(blocked) == 2
    assert agent_run.llm_call_count == 2
    assert agent_run.stopped_by_cap


def test_empty_forced_answer_falls_back_to_apology():
    agent_client = FakeAgentClient([], forced_answer="")

    agent_run = run_agent("q", calculator_registry(), agent_client)

    assert agent_run.final_answer == CAP_REACHED_APOLOGY


def test_repair_resumes_transcript_with_review_feedback():
    agent_client = FakeAgentClient([answer_response("first"), answer_response("fixed")])
    registry = calculator_registry()
    agent_run = run_agent("q", registry, agent_client)

    repaired_answer = repair_agent_answer(agent_run, registry, agent_client, "- drop product X")

    assert repaired_answer == "fixed"
    assert agent_run.final_answer == "fixed"
    assert agent_run.llm_call_count == 2
    repair_input = agent_client.requests[1]["input"]
    assert repair_input[0] == {"role": "user", "content": "q"}
    assert repair_input[-1]["role"] == "developer"
    assert "- drop product X" in repair_input[-1]["content"]


def test_repair_only_gets_leftover_llm_budget():
    first_run_calls = [tool_response(function_call(f"call_{index}")) for index in range(LLM_CAP - 2)]
    agent_client = FakeAgentClient([*first_run_calls, answer_response("first")], forced_answer="forced fix")
    registry = calculator_registry()
    agent_run = run_agent("q", registry, agent_client)
    assert agent_run.llm_call_count == LLM_CAP - 1

    repaired_answer = repair_agent_answer(agent_run, registry, agent_client, "fix it")

    assert agent_run.llm_call_count == LLM_CAP
    assert agent_client.requests[-1]["tool_choice"] == "none"
    assert repaired_answer == agent_run.final_answer == "forced fix"
