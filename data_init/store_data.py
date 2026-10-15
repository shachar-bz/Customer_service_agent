"""Loads every data source the agent's tools read from, in one call."""
from __future__ import annotations

from dataclasses import dataclass

from mongomock.collection import Collection

from data_init.customer_store import get_cust_data_collection
from data_init.product_catalog import Product, index_products_by_id, load_product_catalog
from data_init.product_index import ProductIndex, build_product_index


@dataclass(frozen=True)
class StoreData:
    products_by_id: dict[str, Product]
    product_index: ProductIndex
    customers: Collection


def load_store_data() -> StoreData:
    """Slow on first run: the product index embeds the whole catalog."""
    products = load_product_catalog()
    return StoreData(
        products_by_id=index_products_by_id(products),
        product_index=build_product_index(products),
        customers=get_cust_data_collection(),
    )
