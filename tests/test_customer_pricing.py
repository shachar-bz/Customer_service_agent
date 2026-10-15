from data_init.product_catalog import Product
from pricing.customer_pricing import PREMIER_DISCOUNT_RATE, customer_price, priced_product_view


def make_product(list_price: float, sale_price: float) -> Product:
    return Product(
        uniq_id="p1",
        name="Scale",
        description="",
        list_price=list_price,
        sale_price=sale_price,
        brand="Acme",
        gtin="0",
        category="Body Weight Scales",
        available=True,
    )


def test_regular_customer_pays_sale_price():
    assert customer_price(make_product(120.0, 104.0), 0.0) == 104.0


def test_premier_discount_stacks_on_sale_price():
    # 104.99 is over a $100 budget before the discount and under it after.
    assert customer_price(make_product(120.0, 104.99), PREMIER_DISCOUNT_RATE) == 99.74


def test_priced_view_exposes_both_prices():
    view = priced_product_view(make_product(120.0, 104.0), PREMIER_DISCOUNT_RATE)

    assert view.product_id == "p1"
    assert view.list_price == 120.0
    assert view.sale_price == 104.0
    assert view.on_sale
    assert view.customer_price == 98.8
