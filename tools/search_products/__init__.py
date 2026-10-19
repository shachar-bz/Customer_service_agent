"""search_products tool package: the tool contract plus its private retrieve-then-rerank pipeline."""
from tools.search_products.tool import SEARCH_PRODUCTS_SCHEMA, SearchProductsArgs, search_products

__all__ = [
    "SEARCH_PRODUCTS_SCHEMA",
    "SearchProductsArgs",
    "search_products",
]
