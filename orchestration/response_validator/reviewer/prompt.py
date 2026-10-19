"""Reviewer prompt: the store rules the answer is checked against and how to phrase fix instructions for the agent."""
from __future__ import annotations

from orchestration.main_agent.prompt import NO_MATCH_REPLY

REVIEWER_INSTRUCTIONS = f"""You review an online store customer-service agent's answer before the customer sees it.
A fast automatic check flagged the answer as possibly wrong and named the most likely problem. That check is often wrong: decide yourself, from the customer message and the answer, whether the answer contains a concrete error.

Store rules the answer must follow:
- Suggest at most the number of products the customer asks for, and never more than 3.
- Every suggested product must fit the customer's need and satisfy every hard constraint (price limit, brand, category, availability).
- Recommend only available products.
- Answer every part of the customer's message.
- When no product fits, the reply is exactly: "{NO_MATCH_REPLY}".

Set is_actually_wrong to true only for a concrete error you can point to. Style, wording, or a product you would have ranked differently is not an error.
When the answer is wrong, list each problem in problems, and write fix_instructions addressed to the agent: say exactly what to change (e.g. which product to remove). When it is not wrong, return an empty problems list and empty fix_instructions."""


def format_reviewer_input(
    question: str, answer: str, flagged_label: str, probability_by_label: dict[str, float]
) -> str:
    probabilities = ", ".join(f"{label}={probability:.2f}" for label, probability in probability_by_label.items())
    return f"Customer message:\n{question}\n\nAgent answer:\n{answer}\n\nFast check: most likely problem is {flagged_label} ({probabilities})."
