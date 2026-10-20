"""Reviewer prompt: the store rules the answer is checked against and how to phrase fix instructions for the agent."""
from __future__ import annotations

from typing import Any

from orchestration.main_agent.prompt import NO_MATCH_REPLY
from orchestration.response_validator.response_context import format_product_lines

NO_PRODUCTS_RETRIEVED = "(the agent's tools returned no products)"

REVIEWER_INSTRUCTIONS = f"""You review an online store customer-service agent's answer before the customer sees it.
A fast automatic check flagged the answer as possibly wrong and named the most likely problem. That check is often wrong: decide yourself, from the customer message and the answer, whether the answer contains a concrete error.

Store rules the answer must follow:
- Suggest at most the number of products the customer asks for, and never more than 3.
- Every suggested product must fit the customer's need and satisfy every hard constraint (price limit, brand, category, availability).
- Recommend only available products.
- Every stated price, availability, and product detail must match the retrieved product data (customer_price is the price).
- A recommended product that only supports the need (e.g. tracks it) while a retrieved, available product directly meets it is an error. Name the replacement.
- When the customer asks for recommendations based on their interests, suggest only products in categories from their product interests (given below when looked up).
- Answer every part of the customer's message.
- When no product fits, the reply is exactly: "{NO_MATCH_REPLY}".

You also get every product the agent's tools returned while answering; judge product facts and better alternatives only from this data.
Set is_actually_wrong to true only for a concrete error you can point to. Style, wording, or a different ranking among products that all fit is not an error.
When the answer is wrong, list each problem in problems, and write fix_instructions addressed to the agent: say exactly what to change (e.g. which product to remove). When it is not wrong, return an empty problems list and empty fix_instructions."""


def format_reviewer_input(
    question: str,
    answer: str,
    flagged_label: str,
    probability_by_label: dict[str, float],
    customer_interests: list[str],
    retrieved_products: list[dict[str, Any]],
) -> str:
    probabilities = ", ".join(f"{label}={probability:.2f}" for label, probability in probability_by_label.items())
    interests = f"Customer product interests: {', '.join(customer_interests)}\n\n" if customer_interests else ""
    product_lines = format_product_lines(retrieved_products) if retrieved_products else NO_PRODUCTS_RETRIEVED
    return (
        f"Customer message:\n{question}\n\nAgent answer:\n{answer}\n\n{interests}"
        f"Products the agent's tools returned (customer_price is the price the customer pays):\n{product_lines}\n\n"
        f"Fast check: most likely problem is {flagged_label} ({probabilities})."
    )
