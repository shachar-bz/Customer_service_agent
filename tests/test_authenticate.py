from functools import partial

import pytest

from data_init.customer_store import get_cust_data_collection
from orchestration.session import ConversationSession
from tools.authenticate import INVALID_CREDENTIALS_MESSAGE, AuthenticateArgs, authenticate
from tools.base import execute_tool


@pytest.fixture
def session():
    return ConversationSession()


@pytest.fixture
def run_authenticate(session):
    bound_authenticate = partial(authenticate, get_cust_data_collection(), session)
    return lambda raw_args: execute_tool(AuthenticateArgs, bound_authenticate, raw_args)


def test_premier_customer_gets_discount(run_authenticate, session):
    result = run_authenticate({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})

    assert result == {"full_name": "Amanda Wilson", "status": "premier"}
    assert session.is_premier
    assert session.discount_rate == 0.05


def test_regular_customer_gets_no_discount(run_authenticate, session):
    result = run_authenticate({"email": " Rob.Brown@email.net ", "pw": "OutdoorLife456"})

    assert result == {"full_name": "Rob Brown", "status": "regular"}
    assert not session.is_premier
    assert session.discount_rate == 0.0


def test_wrong_password_and_unknown_email_get_same_error(run_authenticate):
    wrong_password = run_authenticate({"email": "rob.brown@email.net", "pw": "wrong"})
    unknown_email = run_authenticate({"email": "nobody@email.net", "pw": "OutdoorLife456"})

    assert wrong_password == unknown_email == {"error": INVALID_CREDENTIALS_MESSAGE}


def test_failed_attempt_keeps_earlier_login(run_authenticate, session):
    run_authenticate({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})
    run_authenticate({"email": "amanda.wilson@gmail.com", "pw": "wrong"})

    assert session.is_premier


def test_new_login_replaces_earlier_one(run_authenticate, session):
    run_authenticate({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})
    run_authenticate({"email": "rob.brown@email.net", "pw": "OutdoorLife456"})

    assert not session.is_premier


def test_invalid_arguments_return_error(run_authenticate, session):
    missing_password = run_authenticate({"email": "rob.brown@email.net"})
    unexpected_field = run_authenticate({"email": "a@b.c", "pw": "x", "status": "premier"})

    assert "error" in missing_password
    assert "error" in unexpected_field
    assert not session.is_premier
