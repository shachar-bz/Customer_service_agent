from tests.product_factory import make_product
from pricing.customer_pricing import (
    MAX_DESCRIPTION_CHARS,
    PREMIER_DISCOUNT_RATE,
    customer_price,
    priced_product_view,
)


def test_regular_customer_pays_sale_price():
    assert customer_price(make_product(list_price=120.0, sale_price=104.0), 0.0) == 104.0


def test_premier_discount_stacks_on_sale_price():
    # 104.99 is over a $100 budget before the discount and under it after.
    assert customer_price(make_product(list_price=120.0, sale_price=104.99), PREMIER_DISCOUNT_RATE) == 99.74


def test_premier_price_rounds_half_up_not_down_on_float_artifacts():
    # 12.1 * 0.95 is 11.495; float round() gives 11.49, the half-up price is 11.50.
    assert customer_price(make_product(list_price=12.1, sale_price=12.1), PREMIER_DISCOUNT_RATE) == 11.5


def test_priced_view_exposes_both_prices():
    view = priced_product_view(make_product(list_price=120.0, sale_price=104.0), PREMIER_DISCOUNT_RATE)

    assert view.product_id == "p1"
    assert view.list_price == 120.0
    assert view.sale_price == 104.0
    assert view.on_sale
    assert view.customer_price == 98.8
    assert view.available


def test_priced_view_truncates_long_description():
    long_description = "x" * (MAX_DESCRIPTION_CHARS + 50)
    view = priced_product_view(make_product(list_price=120.0, sale_price=104.0, description=long_description), 0.0)

    assert view.description == "x" * MAX_DESCRIPTION_CHARS
