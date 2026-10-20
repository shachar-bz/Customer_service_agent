"""Builds the text the fast validator judges: customer message, agent answer, customer interests (when looked up), and the products the answer recommends."""
from __future__ import annotations

import json
from typing import Any

from orchestration.main_agent.agent import ToolCallRecord

NO_PRODUCTS_RECOMMENDED = "(the answer recommends no products)"


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


def collect_recommended_products(tool_calls: list[ToolCallRecord], answer: str) -> list[dict[str, Any]]:
    """Retrieved products whose name appears in the answer.
    ponytail: exact name match; a product the agent paraphrases is missed, fuzzy match if that happens."""
    return [product for product in collect_retrieved_products(tool_calls) if product["name"] in answer]


def format_response_context(
    question: str, answer: str, products: list[dict[str, Any]], customer_interests: list[str]
) -> str:
    product_lines = (
        "\n".join(json.dumps(product, ensure_ascii=False) for product in products)
        if products
        else NO_PRODUCTS_RECOMMENDED
    )
    interests = f"Customer product interests: {', '.join(customer_interests)}\n\n" if customer_interests else ""
    return (
        f"Customer message:\n{question}\n\n"
        f"Agent answer:\n{answer}\n\n"
        f"{interests}"
        f"Product data of the products the agent recommended (customer_price is the price the customer pays):\n{product_lines}"
    )
