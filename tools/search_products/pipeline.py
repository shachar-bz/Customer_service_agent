"""Semantic product search: retrieve candidates from the vector index, then rerank them with the Decisions API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import OpenAIError

from data_init.product_catalog import Product
from data_init.product_index import ProductIndex
from tools.search_products.reranker import ProductReranker, ProductRerankError

RETRIEVAL_CANDIDATE_COUNT = 15
SEARCH_RESULT_COUNT = 10


@dataclass(frozen=True)
class RankedProduct:
    product: Product
    # None when reranking failed and the order comes from vector distance alone.
    relevance_probability: Optional[float]


@dataclass(frozen=True)
class ProductSearchOutcome:
    ranked_products: list[RankedProduct]
    reranked: bool


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

    def search(self, query: str) -> ProductSearchOutcome:
        """Falls back to vector order when the rerank call fails, so the agent still gets results."""
        matches = self._product_index.search(query, top_k=RETRIEVAL_CANDIDATE_COUNT)
        candidates = [self._products_by_id[match.uniq_id] for match in matches]
        distance_by_id = {match.uniq_id: match.distance for match in matches}
        if not candidates:
            return ProductSearchOutcome(ranked_products=[], reranked=True)

        try:
            reranked_products = self._product_reranker.rerank(query, candidates)
        except (OpenAIError, ProductRerankError):
            return ProductSearchOutcome(
                ranked_products=[
                    RankedProduct(product=product, relevance_probability=None)
                    for product in candidates[:SEARCH_RESULT_COUNT]
                ],
                reranked=False,
            )

        # Equal probabilities (including at the top-10 cutoff) go to the smaller cosine distance.
        reranked_products = sorted(
            reranked_products,
            key=lambda reranked: (-reranked.relevance_probability, distance_by_id[reranked.uniq_id]),
        )
        return ProductSearchOutcome(
            ranked_products=[
                RankedProduct(
                    product=self._products_by_id[reranked.uniq_id],
                    relevance_probability=reranked.relevance_probability,
                )
                for reranked in reranked_products[:SEARCH_RESULT_COUNT]
            ],
            reranked=True,
        )
