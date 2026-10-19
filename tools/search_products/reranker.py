"""Reranks retrieved products against a shopping need with one OpenAI Decisions API predicate question per product."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from openai import OpenAI

from data_init.product_catalog import Product
from data_init.product_index import product_embedding_text

DECISIONS_MODEL = "gpt-6-luna"
RERANK_QUESTION_NAME = "product_satisfies_need"
RERANK_INSTRUCTIONS = (
    "The input is a shopper's need and one product. Does the product satisfy the need?"
)


class ProductRerankError(Exception):
    """The Decisions API answered, but not with a usable predicate answer (e.g. a refusal)."""


@dataclass(frozen=True)
class RerankedProduct:
    uniq_id: str
    # Probability the Decisions API gave that this product satisfies the need.
    relevance_probability: float


def rerank_products(decisions_client: OpenAI, query: str, candidates: list[Product]) -> list[RerankedProduct]:
    """Scores every candidate with its own predicate call (run in parallel).
    Returns scores in the incoming candidate order; the caller does the final ordering."""
    if not candidates:
        return []
    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        return list(executor.map(lambda product: _score_product(decisions_client, query, product), candidates))


def _score_product(decisions_client: OpenAI, query: str, product: Product) -> RerankedProduct:
    decision = decisions_client.decisions.create(
        model=DECISIONS_MODEL,
        input=f"Shopper need: {query}\n\nProduct: {product_embedding_text(product)}",
        questions=[
            {
                "type": "predicate",
                "name": RERANK_QUESTION_NAME,
                "instructions": RERANK_INSTRUCTIONS,
            }
        ],
    )
    answer = next(
        (answer for answer in decision.answers if answer.name == RERANK_QUESTION_NAME),
        None,
    )
    if answer is None or answer.type != "predicate":
        answer_type = "no answer" if answer is None else answer.type
        raise ProductRerankError(f"Expected a predicate answer, got {answer_type}.")
    return RerankedProduct(uniq_id=product.uniq_id, relevance_probability=answer.probability)
