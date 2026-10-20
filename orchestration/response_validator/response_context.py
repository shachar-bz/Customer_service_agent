"""Builds the text the fast validator judges: customer message, agent answer, and the products the agent retrieved."""
from __future__ import annotations

import json
from typing import Any

from orchestration.main_agent.agent import ToolCallRecord

NO_PRODUCTS_RETRIEVED = "(no products were retrieved)"


def collect_retrieved_products(tool_calls: list[ToolCallRecord]) -> list[dict[str, Any]]:
    """Every product view any tool returned, first occurrence wins, in retrieval order."""
    products_by_id: dict[str, dict[str, Any]] = {}
    for tool_call in tool_calls:
        for product in tool_call.result.get("products", []):
            products_by_id.setdefault(product["product_id"], product)
    return list(products_by_id.values())


def collect_customer_interests(tool_calls: list[ToolCallRecord]) -> list[str]:
    """Product interests from every get_customer lookup, deduplicated, in lookup order."""
    interests: dict[str, None] = {}
    for tool_call in tool_calls:
        if tool_call.tool_name == "get_customer":
            interests.update(dict.fromkeys(tool_call.result.get("product_interests", [])))
    return list(interests)


def format_response_context(question: str, answer: str, products: list[dict[str, Any]]) -> str:
    product_lines = (
        "\n".join(json.dumps(product, ensure_ascii=False) for product in products)
        if products
        else NO_PRODUCTS_RETRIEVED
    )
    return (
        f"Customer message:\n{question}\n\n"
        f"Agent answer:\n{answer}\n\n"
        f"Product data the agent retrieved (customer_price is the price the customer pays):\n{product_lines}"
    )
