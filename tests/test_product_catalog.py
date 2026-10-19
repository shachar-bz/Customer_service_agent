import pytest

from data_init.product_catalog import (
    DISCLAIMER_MARKER,
    index_products_by_id,
    load_product_catalog,
    strip_disclaimer,
)

CSV_HEADER = "Uniq Id,Product Name,Description,List Price,Sale Price,Brand,Gtin,Category,Available\n"


@pytest.fixture(scope="module")
def catalog():
    return load_product_catalog()


def test_loads_every_product_in_the_real_catalog(catalog):
    assert len(catalog) == 787
    assert len(index_products_by_id(catalog)) == 787


def test_descriptions_have_no_disclaimer(catalog):
    assert not any(DISCLAIMER_MARKER in product.description for product in catalog)


def test_both_availability_values_are_present(catalog):
    assert {product.available for product in catalog} == {True, False}


def test_strip_disclaimer_keeps_text_without_marker():
    assert strip_disclaimer("  Plain description ") == "Plain description"
    assert strip_disclaimer("Boilerplate. See our disclaimer | Real text") == "Real text"


def test_parses_row_fields(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text(
        CSV_HEADER
        + 'abc123,Digital Thermometer,"Intro. See our disclaimer | Fast reading",12.50,9.99,LHCER,0042,Health | Thermometers,False\n'
    )

    [product] = load_product_catalog(csv_path)

    assert product.uniq_id == "abc123"
    assert product.description == "Fast reading"
    assert product.list_price == 12.50
    assert product.sale_price == 9.99
    assert product.is_on_sale
    assert product.available is False


def test_rejects_missing_columns(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text("Uniq Id,Product Name\nabc,Thing\n")

    with pytest.raises(ValueError, match="missing columns"):
        load_product_catalog(csv_path)


def test_reports_line_of_invalid_price(tmp_path):
    csv_path = tmp_path / "products.csv"
    csv_path.write_text(CSV_HEADER + "abc,Thing,Desc,not-a-price,1.00,Brand,1,Cat,True\n")

    with pytest.raises(ValueError, match="line 2"):
        load_product_catalog(csv_path)
