import logging
from functools import partial
from types import SimpleNamespace

import httpx
import openai
import pytest
from openai.types.decision import Decision

from pricing.conversation_session import ConversationSession
from tests.product_factory import make_product
from data_init.product_index import ProductSearchMatch
from pricing.customer_pricing import PREMIER_DISCOUNT_RATE
from tools.base import execute_tool
from tools.search_products.pipeline import RETRIEVAL_CANDIDATE_COUNT, SEARCH_RESULT_COUNT
from tools.search_products.reranker import RERANK_QUESTION_NAME
from tools.search_products.tool import (
    SearchProductsArgs,
    search_products,
)

CANDIDATE_IDS = [f"product_{position}" for position in range(RETRIEVAL_CANDIDATE_COUNT)]


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
    """Stands in for OpenAI(); answers each per-product predicate call from probability_by_id
    (products missing from it get 0.0), or refuses / raises."""

    def __init__(
        self,
        probability_by_id: dict[str, float] | None = None,
        refuse: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.probability_by_id = probability_by_id or {}
        self.refuse = refuse
        self.error = error
        self.create_calls: list[dict] = []
        self.decisions = SimpleNamespace(create=self.create)

    def create(self, **create_kwargs) -> Decision:
        self.create_calls.append(create_kwargs)
        if self.error is not None:
            raise self.error
        if self.refuse:
            answer = {"type": "refusal", "name": RERANK_QUESTION_NAME}
        else:
            probability = next(
                (
                    probability
                    for uniq_id, probability in self.probability_by_id.items()
                    if f"Name: Item {uniq_id}." in create_kwargs["input"]
                ),
                0.0,
            )
            answer = {"type": "predicate", "name": RERANK_QUESTION_NAME, "probability": probability}
        return Decision.model_validate(
            {
                "answers": [answer],
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


def build_search_tool(decisions_client: FakeDecisionsClient, session=None, uniq_ids=CANDIDATE_IDS):
    product_index = FakeProductIndex(uniq_ids)
    products_by_id = {uniq_id: make_product(uniq_id, sale_price=100.0) for uniq_id in uniq_ids}
    tool = partial(
        search_products, product_index, products_by_id, decisions_client, session or ConversationSession()
    )
    return tool, product_index


def returned_ids(result: dict) -> list[str]:
    # Tool output carries only the short product_id; make_product names each product "Item {uniq_id}".
    return [product["name"].removeprefix("Item ") for product in result["products"]]


def test_makes_one_predicate_call_per_candidate_and_returns_top_ten_by_probability():
    # Reverse of retrieval order: the last retrieved candidate is the most relevant.
    probability_by_id = {uniq_id: (position + 1) / 120 for position, uniq_id in enumerate(CANDIDATE_IDS)}
    decisions_client = FakeDecisionsClient(probability_by_id=probability_by_id)
    tool, product_index = build_search_tool(decisions_client)

    result = execute_tool(SearchProductsArgs, tool, {"query": "  scale with lbs and kg "})

    assert product_index.requested_top_k == RETRIEVAL_CANDIDATE_COUNT
    assert len(decisions_client.create_calls) == RETRIEVAL_CANDIDATE_COUNT
    assert returned_ids(result) == list(reversed(CANDIDATE_IDS))[:SEARCH_RESULT_COUNT]
    assert "note" not in result
    assert all("relevance_probability" not in product for product in result["products"])

    assert all(call["questions"][0]["type"] == "predicate" for call in decisions_client.create_calls)
    assert all("scale with lbs and kg" in call["input"] for call in decisions_client.create_calls)


def test_tie_at_the_cutoff_goes_to_the_earlier_vector_candidate():
    # Candidates are in distance order (product_0 closest). Top 9 are clear; 10th-12th tie.
    probability_by_id = {f"product_{position}": 0.9 for position in range(9)}
    probability_by_id.update({"product_14": 0.5, "product_12": 0.5, "product_10": 0.5})
    tool, _ = build_search_tool(FakeDecisionsClient(probability_by_id=probability_by_id))

    result = tool(query="scale")

    assert returned_ids(result)[-1] == "product_10"
    assert "product_12" not in returned_ids(result)


def test_products_scored_zero_rank_last_in_distance_order():
    tool, _ = build_search_tool(FakeDecisionsClient(probability_by_id={"product_7": 0.9}))

    result = tool(query="scale")

    remaining_ids = [uniq_id for uniq_id in CANDIDATE_IDS if uniq_id != "product_7"]
    assert returned_ids(result) == ["product_7"] + remaining_ids[: SEARCH_RESULT_COUNT - 1]


@pytest.mark.parametrize(
    "decisions_client",
    [
        FakeDecisionsClient(error=openai.APIConnectionError(request=httpx.Request("POST", "https://x"))),
        FakeDecisionsClient(refuse=True),
    ],
    ids=["api_error", "refusal"],
)
def test_falls_back_to_vector_order_when_rerank_fails(decisions_client, caplog):
    tool, _ = build_search_tool(decisions_client)

    with caplog.at_level(logging.WARNING, logger="customer_service_agent"):
        result = tool(query="scale")

    assert returned_ids(result) == CANDIDATE_IDS[:SEARCH_RESULT_COUNT]
    assert "note" not in result
    assert "Rerank failed" in caplog.text and "query='scale'" in caplog.text


def test_out_of_stock_candidates_are_dropped_before_rerank():
    decisions_client = FakeDecisionsClient(probability_by_id={"in_stock": 0.9, "out_of_stock": 1.0})
    products_by_id = {
        "out_of_stock": make_product("out_of_stock", available=False),
        "in_stock": make_product("in_stock"),
    }
    tool = partial(
        search_products, FakeProductIndex(list(products_by_id)), products_by_id, decisions_client, ConversationSession()
    )

    result = tool(query="scale")

    assert returned_ids(result) == ["in_stock"]
    assert len(decisions_client.create_calls) == 1


def test_premier_customer_sees_discounted_customer_price():
    decisions_client = FakeDecisionsClient(probability_by_id={"product_0": 1.0})
    tool, _ = build_search_tool(decisions_client, session=ConversationSession(is_premier=True))

    result = tool(query="scale")

    assert result["products"][0]["customer_price"] == round(100.0 * (1 - PREMIER_DISCOUNT_RATE), 2)


def test_empty_index_returns_no_products():
    decisions_client = FakeDecisionsClient(refuse=True)
    tool, _ = build_search_tool(decisions_client, uniq_ids=[])

    result = tool(query="scale")

    assert result["products"] == []
    assert "note" not in result


@pytest.mark.parametrize("raw_args", [{"query": "   "}, {}, {"query": "scale", "top_k": 3}])
def test_invalid_arguments_return_error(raw_args):
    tool, _ = build_search_tool(FakeDecisionsClient())
    assert "error" in execute_tool(SearchProductsArgs, tool, raw_args)
