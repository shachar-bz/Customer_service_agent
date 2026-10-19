"""Semantic product search: retrieve candidates from the vector index, then rerank them with the Decisions API."""
from __future__ import annotations

import logging

from openai import OpenAIError

from data_init.product_catalog import Product
from data_init.product_index import ProductIndex
from tools.search_products.reranker import ProductReranker, ProductRerankError

RETRIEVAL_CANDIDATE_COUNT = 15
SEARCH_RESULT_COUNT = 10

# Same logger orchestration/logger.py writes agent.log with; looked up by name to avoid importing orchestration.
agent_logger = logging.getLogger("customer_service_agent")


class ProductSearcher:
    def __init__(
        self,
        product_index: ProductIndex,
        products_by_id: dict[str, Product],
        product_reranker: ProductReranker,
    ) -> None:
        self._product_index = product_index
        self._products_by_id = products_by_id
        self._product_reranker = product_reranker

    def search(self, query: str) -> list[Product]:
        """Falls back to vector order when the rerank call fails, so the agent still gets results."""
        matches = self._product_index.search(query, top_k=RETRIEVAL_CANDIDATE_COUNT)
        candidates = [self._products_by_id[match.uniq_id] for match in matches]

        try:
            reranked_products = self._product_reranker.rerank(query, candidates)
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
        return [self._products_by_id[reranked.uniq_id] for reranked in reranked_products[:SEARCH_RESULT_COUNT]]
