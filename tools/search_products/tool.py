"""search_products tool: semantic (RAG) product search for natural-language needs, reranked by the Decisions API."""
from __future__ import annotations

from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from data_init.product_catalog import Product
from data_init.product_index import ProductIndex
from pricing.conversation_session import ConversationSession
from pricing.customer_pricing import priced_product_view
from tools.base import NonBlankStr
from tools.search_products.pipeline import SEARCH_RESULT_COUNT, search_catalog

SEARCH_PRODUCTS_SCHEMA = {
    "type": "function",
    "name": "search_products",
    "description": (
        f"""Semantic search over the product catalog. Use it for natural-language needs
            ("something to keep my coffee hot on the go") and "something like X" requests.
            Returns the {SEARCH_RESULT_COUNT} most relevant products, in stock or not, most
            relevant first; check the available field before recommending. For a category, put
            it in the query. It does not enforce hard constraints (price, brand, sale): to apply
            them, pass the returned product_ids to filter_products with the constraints.
            Prices include the premier discount for a premier customer."""
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The need in natural language, e.g. 'bathroom scale that shows lbs and kg' "
                    "or 'something like the Eufy BodySense Smart Scale'. Use only the customer's "
                    "own words for the need; don't add needs, methods, or product types they did not mention."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "strict": False,
}


class SearchProductsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: NonBlankStr


def search_products(
    product_index: ProductIndex,
    products_by_id: dict[str, Product],
    decisions_client: OpenAI,
    session: ConversationSession,
    query: str,
) -> dict[str, Any]:
    discount_rate = session.discount_rate
    return {
        "products": [
            priced_product_view(product, discount_rate).model_dump()
            for product in search_catalog(product_index, products_by_id, decisions_client, query)
        ],
    }
