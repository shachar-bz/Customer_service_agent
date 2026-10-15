"""search_products tool package: the tool contract plus its private retrieve-then-rerank pipeline."""
from tools.search_products.pipeline import ProductSearcher
from tools.search_products.reranker import ProductReranker, create_decisions_client
from tools.search_products.tool import SEARCH_PRODUCTS_SCHEMA, SearchProductsArgs, search_products

__all__ = [
    "SEARCH_PRODUCTS_SCHEMA",
    "ProductReranker",
    "ProductSearcher",
    "SearchProductsArgs",
    "create_decisions_client",
    "search_products",
]
