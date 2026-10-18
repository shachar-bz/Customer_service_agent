"""Agent runtime: lazily loads and caches the store data and OpenAI clients, then runs one question through the agent."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache

from dotenv import load_dotenv
from openai import OpenAI

from data_init.store_data import StoreData, load_store_data
from orchestration.agent import run_agent
from orchestration.logger import AgentRun
from orchestration.session import ConversationSession
from orchestration.tool_registry import build_tool_registry
from tools.search_products import ProductReranker, ProductSearcher, create_decisions_client

AGENT_API_KEY_ENV_VAR = "OPENAI_API_KEY_AGENT"


@dataclass(frozen=True)
class AgentRuntime:
    """Shared across questions: read-only data and stateless clients."""
    store_data: StoreData
    product_searcher: ProductSearcher
    agent_client: OpenAI


def create_agent_client() -> OpenAI:
    load_dotenv()
    api_key = os.environ.get(AGENT_API_KEY_ENV_VAR)
    if not api_key:
        raise RuntimeError(f"{AGENT_API_KEY_ENV_VAR} is not set (see .env).")
    return OpenAI(api_key=api_key)


@cache
def get_agent_runtime() -> AgentRuntime:
    """Built on the first question (slow: may embed the catalog). A failed build is not cached."""
    store_data = load_store_data()
    product_searcher = ProductSearcher(
        store_data.product_index,
        store_data.products_by_id,
        ProductReranker(create_decisions_client()),
    )
    return AgentRuntime(
        store_data=store_data,
        product_searcher=product_searcher,
        agent_client=create_agent_client(),
    )


def run_customer_service_agent(question: str) -> AgentRun:
    """Each question gets a fresh session, so premier status never leaks between questions."""
    agent_runtime = get_agent_runtime()
    registry = build_tool_registry(
        agent_runtime.store_data, agent_runtime.product_searcher, ConversationSession()
    )
    return run_agent(question, registry, agent_runtime.agent_client)
