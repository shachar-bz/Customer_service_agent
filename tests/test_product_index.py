import chromadb
from chromadb.config import Settings

from data_init.product_catalog import Product
from data_init.product_index import (
    COLLECTION_NAME_PREFIX,
    build_product_index,
    catalog_hash,
)


def make_product(uniq_id: str, name: str, category: str) -> Product:
    return Product(
        uniq_id=uniq_id,
        name=name,
        description=name,
        list_price=10.0,
        sale_price=10.0,
        brand="TestBrand",
        category=category,
        available=True,
    )


SAMPLE_PRODUCTS = [
    make_product("thermometer", "Digital Forehead Thermometer", "Health | Thermometers"),
    make_product("helmet", "Snowboard Helmet with Goggles", "Sports | Snowsports"),
    make_product("soap", "Moisturizing Hand Soap with Aloe", "Bath & Body | Hand Soaps"),
    make_product("scale", "Body Weight Bathroom Scale", "Health | Body Weight Scales"),
]


def open_chroma_client(data_dir):
    return chromadb.PersistentClient(path=str(data_dir), settings=Settings(anonymized_telemetry=False))


def test_search_ranks_the_relevant_product_first(tmp_path):
    product_index = build_product_index(SAMPLE_PRODUCTS, data_dir=tmp_path)

    assert product_index.count() == len(SAMPLE_PRODUCTS)
    assert product_index.search("measure fever temperature", top_k=1)[0].uniq_id == "thermometer"
    assert product_index.search("protect my head while snowboarding", top_k=1)[0].uniq_id == "helmet"


def test_search_returns_closest_first(tmp_path):
    product_index = build_product_index(SAMPLE_PRODUCTS, data_dir=tmp_path)

    matches = product_index.search("hand soap", top_k=4)

    assert len(matches) == 4
    assert [match.distance for match in matches] == sorted(match.distance for match in matches)


def test_reuses_existing_index_for_unchanged_catalog(tmp_path):
    build_product_index(SAMPLE_PRODUCTS, data_dir=tmp_path)
    build_product_index(SAMPLE_PRODUCTS, data_dir=tmp_path)

    assert len(open_chroma_client(tmp_path).list_collections()) == 1


def test_changed_catalog_gets_its_own_collection(tmp_path):
    build_product_index(SAMPLE_PRODUCTS, data_dir=tmp_path)
    changed_index = build_product_index(SAMPLE_PRODUCTS[:2], data_dir=tmp_path)

    assert changed_index.count() == 2
    assert catalog_hash(SAMPLE_PRODUCTS) != catalog_hash(SAMPLE_PRODUCTS[:2])


def test_rebuilds_partially_filled_index(tmp_path):
    collection_name = f"{COLLECTION_NAME_PREFIX}_{catalog_hash(SAMPLE_PRODUCTS)}"
    open_chroma_client(tmp_path).create_collection(collection_name).add(
        ids=["thermometer"], embeddings=[[0.1] * 384], documents=["interrupted build"]
    )

    product_index = build_product_index(SAMPLE_PRODUCTS, data_dir=tmp_path)

    assert product_index.count() == len(SAMPLE_PRODUCTS)
