from data_init.product_catalog import Product
from pricing.customer_pricing import (
    MAX_DESCRIPTION_CHARS,
    PREMIER_DISCOUNT_RATE,
    customer_price,
    priced_product_view,
)


def make_product(list_price: float, sale_price: float, description: str = "") -> Product:
    return Product(
        uniq_id="p1",
        name="Scale",
        description=description,
        list_price=list_price,
        sale_price=sale_price,
        brand="Acme",
        category="Body Weight Scales",
        available=True,
    )


def test_regular_customer_pays_sale_price():
    assert customer_price(make_product(120.0, 104.0), 0.0) == 104.0


def test_premier_discount_stacks_on_sale_price():
    # 104.99 is over a $100 budget before the discount and under it after.
    assert customer_price(make_product(120.0, 104.99), PREMIER_DISCOUNT_RATE) == 99.74


def test_premier_price_rounds_half_up_not_down_on_float_artifacts():
    # 12.1 * 0.95 is 11.495; float round() gives 11.49, the half-up price is 11.50.
    assert customer_price(make_product(12.1, 12.1), PREMIER_DISCOUNT_RATE) == 11.5


def test_priced_view_exposes_both_prices():
    view = priced_product_view(make_product(120.0, 104.0), PREMIER_DISCOUNT_RATE)

    assert view.product_id == "p1"
    assert view.list_price == 120.0
    assert view.sale_price == 104.0
    assert view.on_sale
    assert view.customer_price == 98.8
    assert view.available


def test_priced_view_truncates_long_description():
    long_description = "x" * (MAX_DESCRIPTION_CHARS + 50)
    view = priced_product_view(make_product(120.0, 104.0, long_description), 0.0)

    assert view.description == "x" * MAX_DESCRIPTION_CHARS
