"""search_products tool: semantic (RAG) product search for natural-language needs, reranked by the Decisions API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from orchestration.session import ConversationSession
from pricing.customer_pricing import priced_product_view
from tools.search_products.pipeline import SEARCH_RESULT_COUNT, ProductSearcher

NO_RESULTS_NOTE = "No products found for this query."
RERANK_UNAVAILABLE_NOTE = (
    "Relevance reranking was unavailable; products are ordered by semantic similarity only."
)

SEARCH_PRODUCTS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": (
            f"""Semantic search over the product catalog. Use it for natural-language needs
                ("something to keep my coffee hot on the go") and "something like X" requests.
                Returns the {SEARCH_RESULT_COUNT} most relevant products, most relevant first, each
                with a relevance_probability. It does not enforce hard constraints (price, brand,
                category, availability): use filter_products for those, and check the returned
                fields (e.g. available, customer_price) before recommending.
                Prices include the premier discount for a premier customer."""
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The need in natural language, e.g. 'bathroom scale that shows lbs and kg' "
                        "or 'something like the Eufy BodySense Smart Scale'."
                    ),
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


class SearchProductsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str

    @field_validator("query")
    @classmethod
    def strip_query(cls, query: str) -> str:
        stripped_query = query.strip()
        if not stripped_query:
            raise ValueError("must not be blank")
        return stripped_query


def search_products(
    product_searcher: ProductSearcher,
    session: ConversationSession,
    query: str,
) -> dict[str, Any]:
    search_outcome = product_searcher.search(query)
    discount_rate = session.discount_rate
    result: dict[str, Any] = {
        "products": [
            {
                **priced_product_view(ranked.product, discount_rate).model_dump(),
                "relevance_probability": ranked.relevance_probability,
            }
            for ranked in search_outcome.ranked_products
        ],
    }
    if not search_outcome.ranked_products:
        result["note"] = NO_RESULTS_NOTE
    elif not search_outcome.reranked:
        result["note"] = RERANK_UNAVAILABLE_NOTE
    return result
