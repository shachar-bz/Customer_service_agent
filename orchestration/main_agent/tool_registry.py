"""Tool registry: binds each tool to its dependencies for one conversation and dispatches the LLM's tool calls by name."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

from pydantic import BaseModel

from data_init.store_data import StoreData
from pricing.conversation_session import ConversationSession
from tools.authenticate import AUTHENTICATE_SCHEMA, AuthenticateArgs, authenticate
from tools.base import execute_tool
from tools.calculator import CALCULATOR_SCHEMA, CalculatorArgs, calculator
from tools.filter_products import FILTER_PRODUCTS_SCHEMA, FilterProductsArgs, filter_products
from tools.get_customer import GET_CUSTOMER_SCHEMA, GetCustomerArgs, get_customer
from tools.search_products import (
    SEARCH_PRODUCTS_SCHEMA,
    ProductSearcher,
    SearchProductsArgs,
    search_products,
)

UNKNOWN_TOOL_MESSAGE = "Unknown tool: {tool_name}."
INVALID_ARGUMENTS_JSON_MESSAGE = "Invalid arguments: expected a JSON object."
TOOL_FAILED_MESSAGE = "Tool {tool_name} failed: {error_type}: {error}"


@dataclass(frozen=True)
class RegisteredTool:
    schema: dict[str, Any]
    args_model: type[BaseModel]
    # Dependencies (data, session) already bound via functools.partial.
    function: Callable[..., dict[str, Any]]

    @property
    def name(self) -> str:
        return self.schema["name"]


class ToolRegistry:
    def __init__(self, registered_tools: list[RegisteredTool]) -> None:
        self._tools_by_name = {tool.name: tool for tool in registered_tools}

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [tool.schema for tool in self._tools_by_name.values()]

    def dispatch(self, tool_name: str, raw_arguments_json: str) -> dict[str, Any]:
        """Never raises: every failure comes back as {"error": ...} the LLM can react to."""
        tool = self._tools_by_name.get(tool_name)
        if tool is None:
            return {"error": UNKNOWN_TOOL_MESSAGE.format(tool_name=tool_name)}

        try:
            raw_args = json.loads(raw_arguments_json or "{}")
        except json.JSONDecodeError:
            return {"error": INVALID_ARGUMENTS_JSON_MESSAGE}
        if not isinstance(raw_args, dict):
            return {"error": INVALID_ARGUMENTS_JSON_MESSAGE}

        try:
            return execute_tool(tool.args_model, tool.function, raw_args)
        except Exception as error:
            return {
                "error": TOOL_FAILED_MESSAGE.format(
                    tool_name=tool_name, error_type=type(error).__name__, error=error
                )
            }


def build_tool_registry(
    store_data: StoreData,
    product_searcher: ProductSearcher,
    session: ConversationSession,
) -> ToolRegistry:
    """One registry per conversation: session-aware tools are bound to this conversation's session."""
    products = list(store_data.products_by_id.values())
    return ToolRegistry(
        [
            RegisteredTool(
                AUTHENTICATE_SCHEMA,
                AuthenticateArgs,
                partial(authenticate, store_data.customers, session),
            ),
            RegisteredTool(
                GET_CUSTOMER_SCHEMA,
                GetCustomerArgs,
                partial(get_customer, store_data.customers),
            ),
            RegisteredTool(
                FILTER_PRODUCTS_SCHEMA,
                FilterProductsArgs,
                partial(filter_products, products, session),
            ),
            RegisteredTool(
                SEARCH_PRODUCTS_SCHEMA,
                SearchProductsArgs,
                partial(search_products, product_searcher, session),
            ),
            RegisteredTool(CALCULATOR_SCHEMA, CalculatorArgs, calculator),
        ]
    )
