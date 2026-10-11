from data_init.store_data import load_store_data


def test_loads_all_data_sources_together():
    store_data = load_store_data()

    assert len(store_data.products_by_id) == 787
    assert store_data.product_index.count() == 787
    assert store_data.customers.count_documents({}) == 50
    for match in store_data.product_index.search("thermometer", top_k=3):
        assert match.uniq_id in store_data.products_by_id
