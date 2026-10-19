"""Fast validator prompt: the choice question's instructions and the labels it chooses between."""
from __future__ import annotations

OK_LABEL = "ok"
UNSUITABLE_PRODUCTS_LABEL = "unsuitable_products"
TOO_MANY_PRODUCTS_LABEL = "too_many_products"
QUESTION_NOT_ANSWERED_LABEL = "question_not_answered"

FAST_VALIDATION_INSTRUCTIONS = (
    "The input is a customer's message to an online store's customer-service agent, the agent's "
    "answer, and the product data the agent retrieved from the catalog. Store rules: suggest at "
    "most the number of products the customer asks for and never more than 3; recommend only "
    "available products; quote customer_price as the price. Which choice best describes the answer?"
)

FAST_VALIDATION_CHOICES = [
    {
        "value": OK_LABEL,
        "description": (
            "The answer correctly answers every part of the customer's message. Every suggested "
            "product fits the need, and every stated price, availability and detail matches the "
            "product data. It suggests no more products than allowed."
        ),
    },
    {
        "value": UNSUITABLE_PRODUCTS_LABEL,
        "description": (
            "At least one suggested product does not fit the customer's need or a hard constraint "
            "(price, brand, category, availability), or the answer states a product field (price, "
            "sale, availability, details) that contradicts the product data."
        ),
    },
    {
        "value": TOO_MANY_PRODUCTS_LABEL,
        "description": (
            "The answer suggests more products than the customer asked for, or more than 3 products."
        ),
    },
    {
        "value": QUESTION_NOT_ANSWERED_LABEL,
        "description": (
            "The answer misses or wrongly answers a part of the customer's message, such as a "
            "policy, premier-status or calculation question, or says no product fits when the "
            "product data has one that does."
        ),
    },
]
