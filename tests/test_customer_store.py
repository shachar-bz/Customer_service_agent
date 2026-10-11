from customer_store import get_cust_data_collection


def test_loads_all_customers():
    customers = get_cust_data_collection()
    assert customers.count_documents({}) == 50


def test_finds_customer_by_email_and_password():
    customers = get_cust_data_collection()
    customer = customers.find_one({"email": "rob.brown@email.net", "pw": "OutdoorLife456"})
    assert customer["status"] in {"premier", "regular"}
    assert customer["product-interests"]


def test_wrong_password_finds_nobody():
    customers = get_cust_data_collection()
    assert customers.find_one({"email": "rob.brown@email.net", "pw": "wrong"}) is None
