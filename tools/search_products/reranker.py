"""Reranks retrieved products against a shopping need with one OpenAI Decisions API choice question."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from data_init.product_catalog import Product
from data_init.product_index import product_embedding_text

DECISIONS_MODEL = "gpt-6-luna"
DECISIONS_API_KEY_ENV_VAR = "OPENAI_APY_KEY_DECISIONS"
RERANK_QUESTION_NAME = "best_matching_product"
RERANK_INSTRUCTIONS = (
    "The input is a shopper's need. Choose the product that best satisfies it."
)


class ProductRerankError(Exception):
    """The Decisions API answered, but not with a usable choice (e.g. a refusal)."""


@dataclass(frozen=True)
class RerankedProduct:
    uniq_id: str
    # Probability the Decisions API gave this product as the best match for the need.
    relevance_probability: float


def create_decisions_client() -> OpenAI:
    load_dotenv()
    api_key = os.environ.get(DECISIONS_API_KEY_ENV_VAR)
    if not api_key:
        raise RuntimeError(f"{DECISIONS_API_KEY_ENV_VAR} is not set (see .env).")
    return OpenAI(api_key=api_key)


class ProductReranker:
    def __init__(self, decisions_client: OpenAI) -> None:
        self._decisions_client = decisions_client

    def rerank(self, query: str, candidates: list[Product]) -> list[RerankedProduct]:
        """Returns every candidate, most relevant first. Ties (and products the answer omits,
        scored 0) keep their incoming retrieval order."""
        decision = self._decisions_client.decisions.create(
            model=DECISIONS_MODEL,
            input=f"Shopper need: {query}",
            questions=[
                {
                    "type": "choice",
                    "name": RERANK_QUESTION_NAME,
                    "instructions": RERANK_INSTRUCTIONS,
                    "choices": [
                        {"value": product.uniq_id, "description": product_embedding_text(product)}
                        for product in candidates
                    ],
                }
            ],
        )
        answer = next(
            (answer for answer in decision.answers if answer.name == RERANK_QUESTION_NAME),
            None,
        )
        if answer is None or answer.type != "choice":
            answer_type = "no answer" if answer is None else answer.type
            raise ProductRerankError(f"Expected a choice answer, got {answer_type}.")

        probability_by_id = {
            str(choice_probability.value): choice_probability.probability
            for choice_probability in answer.probabilities
        }
        reranked_products = [
            RerankedProduct(
                uniq_id=product.uniq_id,
                relevance_probability=probability_by_id.get(product.uniq_id, 0.0),
            )
            for product in candidates
        ]
        return sorted(reranked_products, key=lambda reranked: -reranked.relevance_probability)
