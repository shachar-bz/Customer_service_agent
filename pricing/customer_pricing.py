"""Customer-specific pricing: the premier discount and the priced product view tools return."""
from __future__ import annotations

from pydantic import BaseModel

from data_init.product_catalog import Product

PREMIER_DISCOUNT_RATE = 0.05


class PricedProduct(BaseModel):
    product_id: str
    name: str
    brand: str
    category: str
    list_price: float
    sale_price: float
    on_sale: bool
    customer_price: float
    available: bool


def customer_price(product: Product, discount_rate: float) -> float:
    """The discount stacks on sale_price, which equals list_price when the item is not on sale."""
    return round(product.sale_price * (1 - discount_rate), 2)


def priced_product_view(product: Product, discount_rate: float) -> PricedProduct:
    return PricedProduct(
        product_id=product.uniq_id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        list_price=product.list_price,
        sale_price=product.sale_price,
        on_sale=product.is_on_sale,
        customer_price=customer_price(product, discount_rate),
        available=product.available,
    )
