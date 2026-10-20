"""Shared Product builder for tests; every field has a default so each test overrides only what it checks."""

from data_init.product_catalog import Product

DEFAULT_CATEGORY = "Health | Home Health Care | Bathroom Scales | Mechanical Scales"


def make_product(
    uniq_id: str = "p1",
    product_id: int = 1,
    name: str | None = None,
    sale_price: float = 50.0,
    list_price: float | None = None,
    brand: str = "Acme",
    category: str = DEFAULT_CATEGORY,
    available: bool = True,
    description: str = "",
) -> Product:
    return Product(
        product_id=product_id,
        uniq_id=uniq_id,
        name=name if name is not None else f"Item {uniq_id}",
        description=description,
        list_price=list_price if list_price is not None else sale_price,
        sale_price=sale_price,
        brand=brand,
        category=category,
        available=available,
    )
