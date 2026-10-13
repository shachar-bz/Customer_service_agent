"""Loads product_data.csv, the authoritative product catalog, into Product records."""
from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

PRODUCT_CSV_PATH = Path(__file__).resolve().parent.parent / "product_data.csv"

# Most descriptions start with a boilerplate Walmart disclaimer ending with this marker.
DISCLAIMER_MARKER = "See our disclaimer |"

REQUIRED_COLUMNS = {
    "Uniq Id",
    "Product Name",
    "Description",
    "List Price",
    "Sale Price",
    "Brand",
    "Gtin",
    "Category",
    "Available",
}


class Product(BaseModel):
    uniq_id: str
    name: str
    description: str
    list_price: float
    sale_price: float
    brand: str
    gtin: str
    category: str
    available: bool

    @property
    def is_on_sale(self) -> bool:
        return self.sale_price < self.list_price


def strip_disclaimer(description: str) -> str:
    return description.split(DISCLAIMER_MARKER, 1)[-1].strip()


def parse_available(value: str) -> bool:
    normalized_value = value.strip().lower()
    if normalized_value not in {"true", "false"}:
        raise ValueError(f"Invalid Available value: {value!r}")
    return normalized_value == "true"


def product_from_csv_row(row: dict[str, str]) -> Product:
    return Product(
        uniq_id=row["Uniq Id"].strip(),
        name=row["Product Name"].strip(),
        description=strip_disclaimer(row["Description"]),
        list_price=float(row["List Price"]),
        sale_price=float(row["Sale Price"]),
        brand=row["Brand"].strip(),
        gtin=row["Gtin"].strip(),
        category=row["Category"].strip(),
        available=parse_available(row["Available"]),
    )


def load_product_catalog(csv_path: Path = PRODUCT_CSV_PATH) -> list[Product]:
    with open(csv_path, encoding="utf-8-sig", newline="") as catalog_file:
        reader = csv.DictReader(catalog_file)
        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"{csv_path} is missing columns: {sorted(missing_columns)}")

        products: list[Product] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                products.append(product_from_csv_row(row))
            except ValueError as error:
                raise ValueError(f"{csv_path}, line {line_number}: {error}") from error

    return products


def index_products_by_id(products: list[Product]) -> dict[str, Product]:
    return {product.uniq_id: product for product in products}
