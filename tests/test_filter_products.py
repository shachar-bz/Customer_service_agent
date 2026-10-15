from functools import partial

import pytest

from data_init.product_catalog import Product, load_product_catalog
from orchestration.session import ConversationSession
from tools.base import execute_tool
from tools.filter_products import (
    MAX_FILTER_RESULTS,
    NO_FILTER_MESSAGE,
    NO_MATCHES_NOTE,
    FilterProductsArgs,
    filter_products,
)


def make_product(
    uniq_id: str,
    name: str = "Generic Item",
    sale_price: float = 50.0,
    brand: str = "Acme",
    category: str = "Health | Home Health Care | Bathroom Scales | Mechanical Scales",
    available: bool = True,
) -> Product:
    return Product(
        uniq_id=uniq_id,
        name=name,
        description="",
        list_price=sale_price,
        sale_price=sale_price,
        brand=brand,
        gtin="0",
        category=category,
        available=available,
    )


@pytest.fixture
def session():
    return ConversationSession()


def make_runner(products, session):
    bound_filter_products = partial(filter_products, products, session)
    return lambda raw_args: execute_tool(FilterProductsArgs, bound_filter_products, raw_args)


def product_ids(result):
    return [product["product_id"] for product in result["products"]]


def test_price_operators_respect_inclusive_and_exclusive_bounds(session):
    products = [make_product("p99", sale_price=99.0), make_product("p100", sale_price=100.0)]
    run_filter = make_runner(products, session)

    assert product_ids(run_filter({"max_price_exclusive": 100})) == ["p99"]
    assert product_ids(run_filter({"max_price_inclusive": 100})) == ["p99", "p100"]
    assert product_ids(run_filter({"min_price_exclusive": 99})) == ["p100"]
    assert product_ids(run_filter({"min_price_inclusive": 99})) == ["p99", "p100"]


def test_premier_discount_applies_before_price_comparison(session):
    run_filter = make_runner([make_product("p1", sale_price=104.99)], session)

    assert run_filter({"max_price_exclusive": 100})["total_matches"] == 0

    session.is_premier = True
    result = run_filter({"max_price_exclusive": 100})
    assert product_ids(result) == ["p1"]
    assert result["products"][0]["customer_price"] == 99.74


def test_all_filters_combine_with_and(session):
    products = [
        make_product("match", brand="LHCER", sale_price=10.0),
        make_product("wrong_brand", brand="Anself", sale_price=10.0),
        make_product("too_expensive", brand="LHCER", sale_price=30.0),
    ]
    result = make_runner(products, session)({"brand": "lhcer", "max_price_inclusive": 20})

    assert product_ids(result) == ["match"]


def test_brand_is_case_insensitive_exact_match(session):
    products = [make_product("p1", brand="Under Armour")]
    run_filter = make_runner(products, session)

    assert product_ids(run_filter({"brand": " under armour "})) == ["p1"]
    assert run_filter({"brand": "Under"})["total_matches"] == 0


def test_categories_match_whole_levels_and_all_must_hold(session):
    products = [
        make_product("bathroom", category="Health | Home Health Care | Bathroom Scales | All Bathroom Scales"),
        make_product("food", category="Home | Kitchen & Dining | Tools & Gadgets | Food Scales"),
    ]
    run_filter = make_runner(products, session)

    assert product_ids(run_filter({"categories": ["bathroom scales"]})) == ["bathroom"]
    assert product_ids(run_filter({"categories": ["Health", "Bathroom Scales"]})) == ["bathroom"]
    assert run_filter({"categories": ["Health", "Food Scales"]})["total_matches"] == 0
    assert run_filter({"categories": ["scale"]})["total_matches"] == 0


def test_name_contains_matches_name_prefix_only(session):
    run_filter = make_runner([make_product("p1", name="Eufy BodySense Smart Scale")], session)

    assert product_ids(run_filter({"name_contains": "eufy bodysense"})) == ["p1"]
    assert run_filter({"name_contains": "Smart Scale"})["total_matches"] == 0


def test_available_defaults_to_in_stock_and_false_searches_everything(session):
    products = [make_product("in_stock"), make_product("out_of_stock", available=False)]
    run_filter = make_runner(products, session)

    assert product_ids(run_filter({"brand": "Acme"})) == ["in_stock"]
    assert product_ids(run_filter({"brand": "Acme", "available": False})) == ["in_stock", "out_of_stock"]
    assert run_filter({"available": False})["total_matches"] == 2


def test_results_are_capped_in_catalog_order_with_total(session):
    products = [make_product(f"p{index}") for index in range(MAX_FILTER_RESULTS + 5)]
    result = make_runner(products, session)({"brand": "Acme"})

    assert product_ids(result) == [f"p{index}" for index in range(MAX_FILTER_RESULTS)]
    assert result["total_matches"] == MAX_FILTER_RESULTS + 5
    assert "15 matches" in result["note"]


def test_no_matches_returns_empty_list_with_note(session):
    result = make_runner([make_product("p1")], session)({"brand": "Nobody"})

    assert result == {"products": [], "total_matches": 0, "note": NO_MATCHES_NOTE}


def test_no_filter_returns_error(session):
    run_filter = make_runner([make_product("p1")], session)

    assert run_filter({}) == {"error": NO_FILTER_MESSAGE}
    assert run_filter({"available": True}) == {"error": NO_FILTER_MESSAGE}


@pytest.mark.parametrize(
    "raw_args",
    [
        {"max_price_exclusive": 10, "max_price_inclusive": 10},
        {"min_price_exclusive": 10, "min_price_inclusive": 10},
        {"min_price_inclusive": 100, "max_price_exclusive": 50},
        {"max_price_inclusive": -1},
        {"brand": "  "},
        {"categories": []},
        {"categories": ["Health", " "]},
        {"color": "red"},
    ],
)
def test_invalid_arguments_return_error(session, raw_args):
    assert "error" in make_runner([make_product("p1")], session)(raw_args)


def test_real_catalog_results_respect_premier_budget():
    premier_session = ConversationSession(is_premier=True)
    run_filter = make_runner(load_product_catalog(), premier_session)

    result = run_filter({"max_price_inclusive": 11.50})

    assert result["total_matches"] > 0
    assert all(product["customer_price"] <= 11.50 for product in result["products"])
    assert all(product["available"] for product in result["products"])
