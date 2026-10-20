"""filter_products tool: returns catalog products that satisfy every hard constraint (price, brand, categories, name, sale, availability), optionally within a given set of product ids."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from data_init.product_catalog import Product
from pricing.conversation_session import ConversationSession
from pricing.customer_pricing import customer_price, priced_product_view

MAX_FILTER_RESULTS = 10
CATEGORY_LEVEL_SEPARATOR = "|"
NO_FILTER_MESSAGE = (
    "Provide at least one filter: a price bound, brand, categories, name_contains, "
    "on_sale, or available=false. product_ids alone is not a filter."
)
UNKNOWN_PRODUCT_IDS_MESSAGE = "Invalid arguments: unknown product_ids {unknown_product_ids}."
NO_MATCHES_NOTE = "No products match these constraints."
TOO_MANY_MATCHES_NOTE = (
    "Found {total_matches} matches in total; showing the first {shown}. "
    "If you can, call filter_products again with more precise constraints."
)

FILTER_PRODUCTS_SCHEMA = {
    "type": "function",
    "name": "filter_products",
    "description": (
        f"""Find products that satisfy hard constraints. Every argument is optional, and all
            given constraints are combined with AND (a product must satisfy every one).
            Call this whenever the customer states a hard constraint: a price limit, a brand,
            a category, a product name, being on sale, or availability.
            Prices are compared against the customer price, which already includes the
            premier discount for a premier customer.
            To apply constraints to semantic search results, pass their product_ids: only those
            products are considered, and results keep the order of product_ids.
            For "X or Y" requests, call this tool once per alternative and merge the results.
            Returns at most {MAX_FILTER_RESULTS} products; if more match, a note gives the total."""
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "max_price_exclusive": {
                "type": "number",
                "description": "Customer price must be less than this (<). E.g. 'under $100'.",
            },
            "max_price_inclusive": {
                "type": "number",
                "description": "Customer price must be at most this (<=). E.g. 'at most $11.50'.",
            },
            "min_price_exclusive": {
                "type": "number",
                "description": "Customer price must be greater than this (>). E.g. 'over $20'.",
            },
            "min_price_inclusive": {
                "type": "number",
                "description": "Customer price must be at least this (>=). E.g. '$20 or more'.",
            },
            "brand": {
                "type": "string",
                "description": "Exact brand name, case-insensitive, e.g. 'LHCER'.",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Only when the customer explicitly names a category. Each value is one "
                    "category name such as 'Bathroom Scales' or 'Health' (case-insensitive, "
                    "whole name, not a fragment). A product must belong to ALL listed "
                    "categories, so 'health and bathroom scales' -> ['Health', 'Bathroom Scales']."
                ),
            },
            "name_contains": {
                "type": "string",
                "description": (
                    "Only when the customer explicitly names the product. The beginning of the "
                    "product name, case-insensitive: 'Eufy BodySense' matches "
                    "'Eufy BodySense Smart Scale', 'Smart Scale' does not."
                ),
            },
            "product_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Limit the filter to these products, e.g. the product_ids returned by "
                    "search_products. Products outside this list are never returned. Must be "
                    "combined with at least one other constraint."
                ),
            },
            "on_sale": {
                "type": "boolean",
                "description": (
                    "true: only products currently on sale (sale price below list price). "
                    "false: only products not on sale. Omit to ignore sale status."
                ),
            },
            "available": {
                "type": "boolean",
                "description": (
                    "Default true: only products in stock. false: search the whole catalog, "
                    "in stock and out of stock."
                ),
            },
        },
        "additionalProperties": False,
    },
    "strict": False,
}


def normalize_text(text: str) -> str:
    return text.strip().lower()


class FilterProductsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_price_exclusive: Optional[float] = Field(default=None, ge=0)
    max_price_inclusive: Optional[float] = Field(default=None, ge=0)
    min_price_exclusive: Optional[float] = Field(default=None, ge=0)
    min_price_inclusive: Optional[float] = Field(default=None, ge=0)
    brand: Optional[str] = None
    categories: Optional[list[str]] = Field(default=None, min_length=1)
    name_contains: Optional[str] = None
    product_ids: Optional[list[int]] = None
    on_sale: Optional[bool] = None
    available: bool = True

    @field_validator("brand", "name_contains")
    @classmethod
    def normalize_text_filter(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized_value = normalize_text(value)
        if not normalized_value:
            raise ValueError("must not be blank")
        return normalized_value

    @field_validator("categories")
    @classmethod
    def normalize_categories(cls, categories: Optional[list[str]]) -> Optional[list[str]]:
        if categories is None:
            return None
        normalized_categories = [normalize_text(category) for category in categories]
        if not all(normalized_categories):
            raise ValueError("category names must not be blank")
        return normalized_categories

    @field_validator("product_ids")
    @classmethod
    def drop_duplicate_product_ids(cls, product_ids: Optional[list[int]]) -> Optional[list[int]]:
        return None if product_ids is None else list(dict.fromkeys(product_ids))

    @model_validator(mode="after")
    def check_price_bounds(self) -> FilterProductsArgs:
        if self.max_price_exclusive is not None and self.max_price_inclusive is not None:
            raise ValueError("give only one of max_price_exclusive and max_price_inclusive")
        if self.min_price_exclusive is not None and self.min_price_inclusive is not None:
            raise ValueError("give only one of min_price_exclusive and min_price_inclusive")

        upper_bound = self.max_price_exclusive if self.max_price_exclusive is not None else self.max_price_inclusive
        lower_bound = self.min_price_exclusive if self.min_price_exclusive is not None else self.min_price_inclusive
        if upper_bound is not None and lower_bound is not None and lower_bound > upper_bound:
            raise ValueError("the minimum price must not exceed the maximum price")
        return self

    @model_validator(mode="after")
    def require_at_least_one_filter(self) -> FilterProductsArgs:
        # Only available=true (the default) and no constraints: nothing to filter on.
        # product_ids only scopes the other constraints, so it does not count.
        if not self.model_dump(exclude_defaults=True, exclude={"product_ids"}):
            raise ValueError(NO_FILTER_MESSAGE)
        return self


def category_levels(category_path: str) -> set[str]:
    return {normalize_text(level) for level in category_path.split(CATEGORY_LEVEL_SEPARATOR)}


def price_within_bounds(
    price: float,
    max_price_exclusive: Optional[float],
    max_price_inclusive: Optional[float],
    min_price_exclusive: Optional[float],
    min_price_inclusive: Optional[float],
) -> bool:
    if max_price_exclusive is not None and not price < max_price_exclusive:
        return False
    if max_price_inclusive is not None and not price <= max_price_inclusive:
        return False
    if min_price_exclusive is not None and not price > min_price_exclusive:
        return False
    if min_price_inclusive is not None and not price >= min_price_inclusive:
        return False
    return True


def filter_products(
    products: list[Product],
    session: ConversationSession,
    max_price_exclusive: Optional[float],
    max_price_inclusive: Optional[float],
    min_price_exclusive: Optional[float],
    min_price_inclusive: Optional[float],
    brand: Optional[str],
    categories: Optional[list[str]],
    name_contains: Optional[str],
    product_ids: Optional[list[int]],
    on_sale: Optional[bool],
    available: bool,
) -> dict[str, Any]:
    """Text arguments arrive already lowercased and trimmed by FilterProductsArgs.
    With product_ids, only those products are considered, in product_ids order."""
    if product_ids is None:
        scoped_products = products
    else:
        products_by_product_id = {product.product_id: product for product in products}
        unknown_product_ids = [product_id for product_id in product_ids if product_id not in products_by_product_id]
        if unknown_product_ids:
            return {"error": UNKNOWN_PRODUCT_IDS_MESSAGE.format(unknown_product_ids=unknown_product_ids)}
        scoped_products = [products_by_product_id[product_id] for product_id in product_ids]

    discount_rate = session.discount_rate
    matching_products = [
        product
        for product in scoped_products
        if (not available or product.available)
        and (brand is None or normalize_text(product.brand) == brand)
        and (categories is None or set(categories) <= category_levels(product.category))
        and (name_contains is None or normalize_text(product.name).startswith(name_contains))
        and (on_sale is None or product.is_on_sale == on_sale)
        and price_within_bounds(
            customer_price(product, discount_rate),
            max_price_exclusive,
            max_price_inclusive,
            min_price_exclusive,
            min_price_inclusive,
        )
    ]

    shown_products = matching_products[:MAX_FILTER_RESULTS]
    result: dict[str, Any] = {
        "products": [priced_product_view(product, discount_rate).model_dump() for product in shown_products],
        "total_matches": len(matching_products),
    }
    if not matching_products:
        result["note"] = NO_MATCHES_NOTE
    elif len(matching_products) > MAX_FILTER_RESULTS:
        result["note"] = TOO_MANY_MATCHES_NOTE.format(
            total_matches=len(matching_products), shown=len(shown_products)
        )
    return result
