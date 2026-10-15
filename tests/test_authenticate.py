import pytest

from customer_store import get_cust_data_collection
from orchestration.session import ConversationSession
from tools.authenticate import INVALID_CREDENTIALS_MESSAGE, AuthenticateTool


@pytest.fixture
def session():
    return ConversationSession()


@pytest.fixture
def authenticate(session):
    return AuthenticateTool(get_cust_data_collection(), session)


def test_premier_customer_gets_discount(authenticate, session):
    result = authenticate.execute({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})

    assert result == {"full_name": "Amanda Wilson", "status": "premier"}
    assert session.is_premier
    assert session.discount_rate == 0.05


def test_regular_customer_gets_no_discount(authenticate, session):
    result = authenticate.execute({"email": " Rob.Brown@email.net ", "pw": "OutdoorLife456"})

    assert result == {"full_name": "Rob Brown", "status": "regular"}
    assert not session.is_premier
    assert session.discount_rate == 0.0


def test_wrong_password_and_unknown_email_get_same_error(authenticate):
    wrong_password = authenticate.execute({"email": "rob.brown@email.net", "pw": "wrong"})
    unknown_email = authenticate.execute({"email": "nobody@email.net", "pw": "OutdoorLife456"})

    assert wrong_password == unknown_email == {"error": INVALID_CREDENTIALS_MESSAGE}


def test_failed_attempt_keeps_earlier_login(authenticate, session):
    authenticate.execute({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})
    authenticate.execute({"email": "amanda.wilson@gmail.com", "pw": "wrong"})

    assert session.is_premier


def test_new_login_replaces_earlier_one(authenticate, session):
    authenticate.execute({"email": "amanda.wilson@gmail.com", "pw": "HealthTracker789"})
    authenticate.execute({"email": "rob.brown@email.net", "pw": "OutdoorLife456"})

    assert not session.is_premier


def test_invalid_arguments_return_error(authenticate, session):
    missing_password = authenticate.execute({"email": "rob.brown@email.net"})
    unexpected_field = authenticate.execute({"email": "a@b.c", "pw": "x", "status": "premier"})

    assert "error" in missing_password
    assert "error" in unexpected_field
    assert not session.is_premier
