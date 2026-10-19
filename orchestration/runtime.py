"""Agent runtime: lazily loads and caches the store data and OpenAI clients, then runs one question through the agent and response validation."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache, partial

from dotenv import load_dotenv
from openai import OpenAI

from data_init.store_data import StoreData, load_store_data
from orchestration.main_agent.agent import repair_agent_answer, run_agent
from orchestration.question_outcome import QuestionOutcome
from orchestration.response_validator.fast_validator import run_fast_validation
from orchestration.response_validator.pipeline import validate_response
from orchestration.response_validator.reviewer import review_response
from pricing.conversation_session import ConversationSession
from orchestration.main_agent.tool_registry import build_tool_registry

AGENT_API_KEY_ENV_VAR = "OPENAI_API_KEY_AGENT"
DECISIONS_API_KEY_ENV_VAR = "OPENAI_API_KEY_DECISIONS"


@dataclass(frozen=True)
class AgentRuntime:
    """Shared across questions: read-only data and stateless clients."""
    store_data: StoreData
    agent_client: OpenAI
    decisions_client: OpenAI


def create_openai_client(api_key_env_var: str) -> OpenAI:
    load_dotenv()
    api_key = os.environ.get(api_key_env_var)
    if not api_key:
        raise RuntimeError(f"{api_key_env_var} is not set (see .env).")
    return OpenAI(api_key=api_key)


@cache
def get_agent_runtime() -> AgentRuntime:
    """Built on the first question (slow: may embed the catalog). A failed build is not cached."""
    store_data = load_store_data()
    decisions_client = create_openai_client(DECISIONS_API_KEY_ENV_VAR)
    agent_client = create_openai_client(AGENT_API_KEY_ENV_VAR)
    return AgentRuntime(
        store_data=store_data,
        agent_client=agent_client,
        decisions_client=decisions_client,
    )


def run_customer_service_agent(question: str) -> QuestionOutcome:
    """Each question gets a fresh session, so premier status never leaks between questions."""
    agent_runtime = get_agent_runtime()
    registry = build_tool_registry(
        agent_runtime.store_data, agent_runtime.decisions_client, ConversationSession()
    )
    agent_run = run_agent(question, registry, agent_runtime.agent_client)
    # The repair reuses this question's registry, so the session (premier status) carries over.
    response_validation = validate_response(
        agent_run,
        fast_validate=partial(run_fast_validation, agent_runtime.decisions_client),
        # The reviewer is billed on the agent key; the fast validator on the Decisions key.
        review_response=partial(review_response, agent_runtime.agent_client),
        repair_answer=lambda review_feedback: repair_agent_answer(
            agent_run, registry, agent_runtime.agent_client, review_feedback
        ),
    )
    return QuestionOutcome(agent_run=agent_run, response_validation=response_validation)
