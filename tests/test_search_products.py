from functools import partial
from types import SimpleNamespace

import httpx
import openai
import pytest
from openai.types.decision import Decision

from data_init.product_catalog import Product
from orchestration.session import ConversationSession
from data_init.product_index import ProductSearchMatch
from pricing.customer_pricing import PREMIER_DISCOUNT_RATE
from tools.base import execute_tool
from tools.search_products.pipeline import RETRIEVAL_CANDIDATE_COUNT, SEARCH_RESULT_COUNT, ProductSearcher
from tools.search_products.reranker import RERANK_QUESTION_NAME, ProductRerankError, ProductReranker
from tools.search_products.tool import (
    NO_RESULTS_NOTE,
    RERANK_UNAVAILABLE_NOTE,
    SearchProductsArgs,
    search_products,
)

CANDIDATE_IDS = [f"product_{position}" for position in range(RETRIEVAL_CANDIDATE_COUNT)]


def make_product(uniq_id: str, sale_price: float = 100.0) -> Product:
    return Product(
        uniq_id=uniq_id,
        name=f"Item {uniq_id}",
        description="",
        list_price=sale_price,
        sale_price=sale_price,
        brand="Acme",
        gtin="0",
        category="Health | Scales",
        available=True,
    )


class FakeProductIndex:
    def __init__(self, uniq_ids: list[str]) -> None:
        self.uniq_ids = uniq_ids
        self.requested_top_k = None

    def search(self, phrase: str, top_k: int) -> list[ProductSearchMatch]:
        self.requested_top_k = top_k
        return [
            ProductSearchMatch(uniq_id=uniq_id, distance=position / 100)
            for position, uniq_id in enumerate(self.uniq_ids[:top_k])
        ]


class FakeDecisionsClient:
    """Stands in for OpenAI(); returns a fixed answer list, or raises."""

    def __init__(self, answers: list[dict] | None = None, error: Exception | None = None) -> None:
        self.answers = answers
        self.error = error
        self.create_kwargs = None
        self.decisions = SimpleNamespace(create=self.create)

    def create(self, **create_kwargs) -> Decision:
        self.create_kwargs = create_kwargs
        if self.error is not None:
            raise self.error
        return Decision.model_validate(
            {
                "answers": self.answers,
                "model": "gpt-6-luna",
                "usage": {
                    "input_tokens": 1,
                    "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
                    "output_tokens": 0,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 1,
                },
            }
        )


def choice_answer(probability_by_id: dict[str, float]) -> dict:
    best_id = max(probability_by_id, key=probability_by_id.get)
    return {
        "type": "choice",
        "name": RERANK_QUESTION_NAME,
        "choice": best_id,
        "confidence": probability_by_id[best_id],
        "probabilities": [
            {"value": uniq_id, "probability": probability}
            for uniq_id, probability in probability_by_id.items()
        ],
    }


def build_search_tool(decisions_client: FakeDecisionsClient, session=None, uniq_ids=CANDIDATE_IDS):
    product_index = FakeProductIndex(uniq_ids)
    products_by_id = {uniq_id: make_product(uniq_id) for uniq_id in uniq_ids}
    product_searcher = ProductSearcher(product_index, products_by_id, ProductReranker(decisions_client))
    tool = partial(search_products, product_searcher, session or ConversationSession())
    return tool, product_index


def returned_ids(result: dict) -> list[str]:
    return [product["product_id"] for product in result["products"]]


def test_reranks_fifteen_candidates_and_returns_top_ten_by_probability():
    # Reverse of retrieval order: the last retrieved candidate is the most relevant.
    probability_by_id = {uniq_id: (position + 1) / 120 for position, uniq_id in enumerate(CANDIDATE_IDS)}
    decisions_client = FakeDecisionsClient(answers=[choice_answer(probability_by_id)])
    tool, product_index = build_search_tool(decisions_client)

    result = execute_tool(SearchProductsArgs, tool, {"query": "  scale with lbs and kg "})

    assert product_index.requested_top_k == RETRIEVAL_CANDIDATE_COUNT
    assert returned_ids(result) == list(reversed(CANDIDATE_IDS))[:SEARCH_RESULT_COUNT]
    assert result["products"][0]["relevance_probability"] == probability_by_id["product_14"]
    assert "note" not in result

    question = decisions_client.create_kwargs["questions"][0]
    assert question["type"] == "choice"
    assert [choice["value"] for choice in question["choices"]] == CANDIDATE_IDS
    assert "scale with lbs and kg" in decisions_client.create_kwargs["input"]


def test_products_missing_from_the_answer_rank_last_in_retrieval_order():
    decisions_client = FakeDecisionsClient(answers=[choice_answer({"product_7": 0.9})])
    tool, _ = build_search_tool(decisions_client)

    result = tool(query="scale")

    remaining_ids = [uniq_id for uniq_id in CANDIDATE_IDS if uniq_id != "product_7"]
    assert returned_ids(result) == ["product_7"] + remaining_ids[: SEARCH_RESULT_COUNT - 1]
    assert result["products"][1]["relevance_probability"] == 0.0


@pytest.mark.parametrize(
    "decisions_client",
    [
        FakeDecisionsClient(error=openai.APIConnectionError(request=httpx.Request("POST", "https://x"))),
        FakeDecisionsClient(answers=[{"type": "refusal", "name": RERANK_QUESTION_NAME}]),
    ],
    ids=["api_error", "refusal"],
)
def test_falls_back_to_vector_order_when_rerank_fails(decisions_client):
    tool, _ = build_search_tool(decisions_client)

    result = tool(query="scale")

    assert returned_ids(result) == CANDIDATE_IDS[:SEARCH_RESULT_COUNT]
    assert all(product["relevance_probability"] is None for product in result["products"])
    assert result["note"] == RERANK_UNAVAILABLE_NOTE


def test_refusal_raises_rerank_error():
    reranker = ProductReranker(FakeDecisionsClient(answers=[{"type": "refusal", "name": RERANK_QUESTION_NAME}]))
    with pytest.raises(ProductRerankError):
        reranker.rerank("scale", [make_product("a")])


def test_premier_customer_sees_discounted_customer_price():
    decisions_client = FakeDecisionsClient(answers=[choice_answer({"product_0": 1.0})])
    tool, _ = build_search_tool(decisions_client, session=ConversationSession(is_premier=True))

    result = tool(query="scale")

    assert result["products"][0]["customer_price"] == round(100.0 * (1 - PREMIER_DISCOUNT_RATE), 2)


def test_empty_index_returns_note():
    decisions_client = FakeDecisionsClient(answers=[{"type": "refusal", "name": RERANK_QUESTION_NAME}])
    tool, _ = build_search_tool(decisions_client, uniq_ids=[])

    result = tool(query="scale")

    assert result["products"] == []
    assert result["note"] == NO_RESULTS_NOTE


@pytest.mark.parametrize("raw_args", [{"query": "   "}, {}, {"query": "scale", "top_k": 3}])
def test_invalid_arguments_return_error(raw_args):
    tool, _ = build_search_tool(FakeDecisionsClient(answers=[]))
    assert "error" in execute_tool(SearchProductsArgs, tool, raw_args)
