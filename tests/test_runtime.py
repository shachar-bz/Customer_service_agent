"""Runtime wiring: run_customer_service_agent passes the pipeline's validation and repaired answer into QuestionOutcome. No real OpenAI calls."""
import orchestration.runtime
from orchestration.main_agent.agent import AgentRun
from orchestration.response_validator.fast_validator import FastValidationResult
from orchestration.response_validator.reviewer import ResponseReview, ResponseReviewVerdict
from orchestration.runtime import AgentRuntime, run_customer_service_agent

FAKE_AGENT_CLIENT = object()
FAKE_REGISTRY = object()


def flagging_fast_validation(decisions_client, question, answer, products, customer_interests):
    return FastValidationResult({"ok": 0.1, "too_many_products": 0.9}, latency_ms=1.0)


def confirming_review(reviewer_client, question, answer, flagged_label, probability_by_label, customer_interests):
    verdict = ResponseReviewVerdict(is_actually_wrong=True, problems=["4 products"], fix_instructions="Keep 3.")
    return ResponseReview(verdict=verdict, latency_ms=1.0)


def install_fake_runtime(monkeypatch):
    """Replaces the cached runtime and the agent calls; returns the recorded repair calls."""
    fake_runtime = AgentRuntime(
        store_data=object(),
        agent_client=FAKE_AGENT_CLIENT,
        decisions_client=object(),
    )
    repair_calls = []

    def fake_run_agent(question, registry, agent_client):
        return AgentRun(question=question, final_answer="original")

    def fake_repair_agent_answer(agent_run, registry, agent_client, review_feedback):
        # Like the real repair: agent_run.final_answer stays the original, only the return value is repaired.
        repair_calls.append((agent_run, registry, agent_client, review_feedback))
        return "repaired"

    monkeypatch.setattr(orchestration.runtime, "get_agent_runtime", lambda: fake_runtime)
    monkeypatch.setattr(orchestration.runtime, "build_tool_registry", lambda *args: FAKE_REGISTRY)
    monkeypatch.setattr(orchestration.runtime, "run_agent", fake_run_agent)
    monkeypatch.setattr(orchestration.runtime, "repair_agent_answer", fake_repair_agent_answer)
    monkeypatch.setattr(orchestration.runtime, "run_fast_validation", flagging_fast_validation)
    monkeypatch.setattr(orchestration.runtime, "review_response", confirming_review)
    return repair_calls


def test_repaired_answer_reaches_question_outcome(monkeypatch):
    repair_calls = install_fake_runtime(monkeypatch)

    question_outcome = run_customer_service_agent("q")

    assert question_outcome.final_answer == "repaired"
    assert question_outcome.agent_run.final_answer == "original"
    assert question_outcome.response_validation.original_answer == "original"
    assert question_outcome.response_validation.review is not None
    [(agent_run, registry, agent_client, review_feedback)] = repair_calls
    assert agent_run is question_outcome.agent_run
    assert registry is FAKE_REGISTRY and agent_client is FAKE_AGENT_CLIENT
    assert review_feedback == "- 4 products\nHow to fix: Keep 3."
