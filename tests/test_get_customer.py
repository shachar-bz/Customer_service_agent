from functools import partial

import pytest

from customer_store import get_cust_data_collection
from tools.base import execute_tool
from tools.get_customer import NO_CUSTOMER_FOUND_MESSAGE, GetCustomerArgs, get_customer

MICHELLE_GARCIA = {
    "full_name": "Michelle Garcia",
    "product_interests": ["Snowsports", "Bikes", "Water Sports"],
}


@pytest.fixture
def run_get_customer():
    bound_get_customer = partial(get_customer, get_cust_data_collection())
    return lambda raw_args: execute_tool(GetCustomerArgs, bound_get_customer, raw_args)


def test_lookup_by_email_ignores_case_and_whitespace(run_get_customer):
    result = run_get_customer({"email": "  Michelle.Garcia@GMAIL.com "})

    assert result == MICHELLE_GARCIA


@pytest.mark.parametrize("name", ["michelle garcia", "  Michelle   Garcia ", "MICHELLE GARCIA"])
def test_lookup_by_full_name_ignores_case_and_whitespace(run_get_customer, name):
    assert run_get_customer({"name": name}) == MICHELLE_GARCIA


def test_lookup_by_matching_email_and_name(run_get_customer):
    result = run_get_customer({"email": "michelle.garcia@gmail.com", "name": "Michelle Garcia"})

    assert result == MICHELLE_GARCIA


def test_email_and_name_of_different_customers_not_found(run_get_customer):
    result = run_get_customer({"email": "rob.brown@email.net", "name": "Michelle Garcia"})

    assert result == {"error": NO_CUSTOMER_FOUND_MESSAGE}


@pytest.mark.parametrize("name", ["Michelle", "Garcia", "Michelle Garc", "Nobody Here"])
def test_partial_or_unknown_name_not_found(run_get_customer, name):
    assert run_get_customer({"name": name}) == {"error": NO_CUSTOMER_FOUND_MESSAGE}


def test_unknown_email_not_found(run_get_customer):
    assert run_get_customer({"email": "nobody@email.net"}) == {"error": NO_CUSTOMER_FOUND_MESSAGE}


def test_result_exposes_only_name_and_interests(run_get_customer):
    result = run_get_customer({"email": "rob.brown@email.net"})

    assert set(result) == {"full_name", "product_interests"}


@pytest.mark.parametrize(
    "raw_args",
    [{}, {"email": "   "}, {"name": ""}, {"email": "rob.brown@email.net", "pw": "OutdoorLife456"}],
)
def test_invalid_arguments_return_error(run_get_customer, raw_args):
    result = run_get_customer(raw_args)

    assert set(result) == {"error"}
    assert result["error"].startswith("Invalid arguments")
