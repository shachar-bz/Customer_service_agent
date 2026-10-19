from types import SimpleNamespace

import pytest

from orchestration.agent import ToolCallRecord
from orchestration.response_validator.fast_validator import (
    OK_LABEL,
    FastValidationError,
    FastValidator,
)
from orchestration.response_validator.fast_validator.fast_validator import FAST_VALIDATION_QUESTION_NAME
from orchestration.response_validator.fast_validator.prompt import (
    FAST_VALIDATION_CHOICES,
    TOO_MANY_PRODUCTS_LABEL,
)
from orchestration.response_validator.response_context import (
    NO_PRODUCTS_RETRIEVED,
    collect_retrieved_products,
    format_response_context,
)


def choice_answer(probability_by_label, name=FAST_VALIDATION_QUESTION_NAME, answer_type="choice"):
    return SimpleNamespace(
        name=name,
        type=answer_type,
        probabilities=[
            SimpleNamespace(value=label, probability=probability)
            for label, probability in probability_by_label.items()
        ],
    )


class FakeDecisionsClient:
    def __init__(self, answers):
        self._answers = answers
        self.requests = []
        self.decisions = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(answers=self._answers)


def test_sends_one_choice_question_with_all_labels_and_context():
    decisions_client = FakeDecisionsClient([choice_answer({OK_LABEL: 0.9})])

    FastValidator(decisions_client).validate("need a mug", "1. Mug - $5", [{"product_id": "p1"}])

    [request] = decisions_client.requests
    [question] = request["questions"]
    assert question["type"] == "choice"
    assert question["choices"] == FAST_VALIDATION_CHOICES
    assert "need a mug" in request["input"] and "1. Mug - $5" in request["input"]
    assert '"product_id": "p1"' in request["input"]


def test_ok_probability_at_threshold_passes():
    decisions_client = FakeDecisionsClient([choice_answer({OK_LABEL: 0.5, TOO_MANY_PRODUCTS_LABEL: 0.5})])

    result = FastValidator(decisions_client).validate("q", "a", [])

    assert result.is_ok


def test_low_ok_probability_fails_with_most_likely_problem():
    decisions_client = FakeDecisionsClient([choice_answer({OK_LABEL: 0.3, TOO_MANY_PRODUCTS_LABEL: 0.7})])

    result = FastValidator(decisions_client).validate("q", "a", [])

    assert not result.is_ok
    assert result.most_likely_label == TOO_MANY_PRODUCTS_LABEL


@pytest.mark.parametrize(
    "answers",
    [[], [choice_answer({OK_LABEL: 1.0}, answer_type="refusal")], [choice_answer({})]],
)
def test_unusable_answer_raises(answers):
    with pytest.raises(FastValidationError):
        FastValidator(FakeDecisionsClient(answers)).validate("q", "a", [])


def tool_call_with_products(*product_ids):
    return ToolCallRecord(
        tool_name="search_products",
        raw_arguments_json="{}",
        result={"products": [{"product_id": product_id, "name": product_id} for product_id in product_ids]},
        error=None,
        latency_ms=0.0,
    )


def test_collects_products_once_in_retrieval_order():
    calculator_call = ToolCallRecord("calculator", "{}", {"result": 2}, None, 0.0)
    tool_calls = [tool_call_with_products("a", "b"), calculator_call, tool_call_with_products("b", "c")]

    products = collect_retrieved_products(tool_calls)

    assert [product["product_id"] for product in products] == ["a", "b", "c"]


def test_context_says_when_no_products_were_retrieved():
    assert NO_PRODUCTS_RETRIEVED in format_response_context("q", "a", [])
