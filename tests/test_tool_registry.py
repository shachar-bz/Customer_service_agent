import json

import pytest

from data_init.customer_store import get_cust_data_collection
from data_init.product_catalog import index_products_by_id, load_product_catalog
from data_init.store_data import StoreData
from orchestration.session import ConversationSession
from orchestration.tool_registry import (
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
        products_by_id=index_products_by_id(load_product_catalog()),
        product_index=None,
        customers=get_cust_data_collection(),
    )
    # search_products is not exercised here, so no real searcher (index, Decisions API) is needed.
    return build_tool_registry(store_data, product_searcher=None, session=session)


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


@pytest.mark.parametrize("raw_arguments_json", ["not json", "[1, 2]"])
def test_malformed_arguments_return_error(registry, raw_arguments_json):
    assert registry.dispatch("calculator", raw_arguments_json) == {
        "error": INVALID_ARGUMENTS_JSON_MESSAGE
    }


def test_invalid_arguments_return_validation_error(registry):
    assert "Invalid arguments" in registry.dispatch("calculator", "{}")["error"]


def test_tool_exception_is_returned_as_error():
    def exploding_calculator(expression):
        raise RuntimeError("boom")

    registry = ToolRegistry([RegisteredTool(CALCULATOR_SCHEMA, CalculatorArgs, exploding_calculator)])

    result = registry.dispatch("calculator", json.dumps({"expression": "1"}))

    assert result == {"error": "Tool calculator failed: RuntimeError: boom"}
