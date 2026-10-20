"""Semantic product search: retrieve candidates from the vector index, then rerank them with the Decisions API."""
from __future__ import annotations

import logging

from openai import OpenAI, OpenAIError

from data_init.product_catalog import Product
from data_init.product_index import ProductIndex
from tools.search_products.reranker import ProductRerankError, rerank_products

RETRIEVAL_CANDIDATE_COUNT = 15
SEARCH_RESULT_COUNT = 10

# Same logger orchestration/logger.py writes agent.log with; looked up by name to avoid importing orchestration.
agent_logger = logging.getLogger("customer_service_agent")


def search_catalog(
    product_index: ProductIndex,
    products_by_id: dict[str, Product],
    decisions_client: OpenAI,
    query: str,
) -> list[Product]:
    """Returns in-stock products only; out-of-stock candidates are dropped before rerank.
    Falls back to vector order when the rerank call fails, so the agent still gets results."""
    matches = product_index.search(query, top_k=RETRIEVAL_CANDIDATE_COUNT)
    candidates = [products_by_id[match.uniq_id] for match in matches if products_by_id[match.uniq_id].available]

    try:
        reranked_products = rerank_products(decisions_client, query, candidates)
    except (OpenAIError, ProductRerankError) as rerank_error:
        agent_logger.warning(
            "Rerank failed, falling back to vector order. query=%r error=%s: %s",
            query,
            type(rerank_error).__name__,
            rerank_error,
        )
        return candidates[:SEARCH_RESULT_COUNT]

    # sorted is stable and candidates are in vector-distance order, so equal probabilities
    # (including at the top-10 cutoff) go to the smaller cosine distance.
    reranked_products = sorted(reranked_products, key=lambda reranked: -reranked.relevance_probability)
    return [products_by_id[reranked.uniq_id] for reranked in reranked_products[:SEARCH_RESULT_COUNT]]
