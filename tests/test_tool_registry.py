import json

import pytest

from data_init.customer_store import get_cust_data_collection
from data_init.store_data import StoreData
from pricing.conversation_session import ConversationSession
from orchestration.main_agent.tool_registry import (
    INVALID_ARGUMENTS_JSON_MESSAGE,
    RegisteredTool,
    ToolRegistry,
    build_tool_registry,
)
from tools.calculator import CALCULATOR_SCHEMA, CalculatorArgs


@pytest.fixture
def session():
    return ConversationSession()


@pytest.fixture
def registry(session):
    store_data = StoreData(
        products_by_id={},
        product_index=None,
        customers=get_cust_data_collection(),
    )
    # search_products is not exercised here, so no real index or Decisions client is needed.
    return build_tool_registry(store_data, decisions_client=None, session=session)


def test_exposes_every_tool_schema(registry):
    assert {schema["name"] for schema in registry.tool_schemas} == {
        "authenticate",
        "get_customer",
        "filter_products",
        "search_products",
        "calculator",
    }


def test_dispatches_by_name(registry):
    assert registry.dispatch("calculator", json.dumps({"expression": "2 + 3"})) == {"result": 5}


def test_authenticate_updates_the_bound_session(registry, session):
    registry.dispatch(
        "authenticate", json.dumps({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})
    )
    assert session.is_premier


def test_unknown_tool_returns_error(registry):
    assert "Unknown tool" in registry.dispatch("delete_everything", "{}")["error"]


def test_malformed_json_returns_error(registry):
    assert registry.dispatch("calculator", "not json") == {"error": INVALID_ARGUMENTS_JSON_MESSAGE}


def test_tool_exception_is_returned_as_error():
    def exploding_calculator(expression):
        raise RuntimeError("boom")

    registry = ToolRegistry([RegisteredTool(CALCULATOR_SCHEMA, CalculatorArgs, exploding_calculator)])

    result = registry.dispatch("calculator", json.dumps({"expression": "1"}))

    assert result == {"error": "Tool calculator failed: RuntimeError: boom"}
