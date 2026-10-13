"""Semantic vector index over the product catalog, persisted with Chroma.

The collection name includes a hash of the catalog, so editing the CSV builds a fresh
index while unchanged data reuses the one on disk.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from data_init.product_catalog import Product, load_product_catalog

CHROMA_DATA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME_PREFIX = "products"
CATALOG_HASH_LENGTH = 12
ADD_BATCH_SIZE = 500


@dataclass(frozen=True)
class ProductSearchMatch:
    uniq_id: str
    # Cosine distance: 0 is identical, larger is less similar.
    distance: float


def product_embedding_text(product: Product) -> str:
    # Name and category come first: the embedding model truncates long descriptions.
    return (
        f"Name: {product.name}. "
        f"Category: {product.category}. "
        f"Brand: {product.brand}. "
        f"Description: {product.description}"
    )


def catalog_hash(products: list[Product]) -> str:
    hash_builder = hashlib.sha256()
    for product in products:
        hash_builder.update(product_embedding_text(product).encode("utf-8"))
        hash_builder.update(product.uniq_id.encode("utf-8"))
    return hash_builder.hexdigest()[:CATALOG_HASH_LENGTH]


class ProductIndex:
    def __init__(self, collection: chromadb.Collection) -> None:
        self._collection = collection

    def count(self) -> int:
        return self._collection.count()

    def search(self, phrase: str, top_k: int) -> list[ProductSearchMatch]:
        result = self._collection.query(query_texts=[phrase], n_results=top_k)
        return [
            ProductSearchMatch(uniq_id=uniq_id, distance=distance)
            for uniq_id, distance in zip(result["ids"][0], result["distances"][0])
        ]


def _create_embedding_function() -> SentenceTransformerEmbeddingFunction:
    # Keeps transformers from importing TensorFlow when it happens to be installed.
    os.environ.setdefault("USE_TF", "0")
    return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)


def _open_collection(client: chromadb.ClientAPI, collection_name: str) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=_create_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def build_product_index(
    products: list[Product],
    data_dir: Path = CHROMA_DATA_DIR,
) -> ProductIndex:
    """Returns the persisted index for this catalog, embedding the products only if needed."""
    client = chromadb.PersistentClient(
        path=str(data_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    collection_name = f"{COLLECTION_NAME_PREFIX}_{catalog_hash(products)}"
    collection = _open_collection(client, collection_name)

    if collection.count() == len(products):
        return ProductIndex(collection)

    # Left partially filled by an interrupted build: start over.
    if collection.count() > 0:
        client.delete_collection(collection_name)
        collection = _open_collection(client, collection_name)

    for batch_start in range(0, len(products), ADD_BATCH_SIZE):
        product_batch = products[batch_start : batch_start + ADD_BATCH_SIZE]
        collection.add(
            ids=[product.uniq_id for product in product_batch],
            documents=[product_embedding_text(product) for product in product_batch],
        )

    return ProductIndex(collection)
