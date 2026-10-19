import json
from types import SimpleNamespace

import pytest

from orchestration.response_validator.reviewer import ResponseReviewer, ResponseReviewError
from orchestration.response_validator.reviewer.reviewer import REVIEWER_MODEL


class FakeReviewerClient:
    def __init__(self, output_text):
        self._output_text = output_text
        self.requests = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(output_text=self._output_text)


def verdict_json(is_actually_wrong, problems=(), fix_instructions=""):
    return json.dumps(
        {"is_actually_wrong": is_actually_wrong, "problems": list(problems), "fix_instructions": fix_instructions}
    )


def test_single_tool_free_call_with_context_and_flagged_label():
    reviewer_client = FakeReviewerClient(verdict_json(False))

    review = ResponseReviewer(reviewer_client).review("CONTEXT", "too_many_products", {"ok": 0.2})

    [request] = reviewer_client.requests
    assert request["model"] == REVIEWER_MODEL
    assert "tools" not in request
    assert request["text"]["format"]["type"] == "json_schema"
    assert "CONTEXT" in request["input"] and "too_many_products" in request["input"]
    assert not review.verdict.is_actually_wrong


def test_wrong_verdict_becomes_review_feedback():
    reviewer_client = FakeReviewerClient(verdict_json(True, ["4 products listed"], "Keep the best 3."))

    review = ResponseReviewer(reviewer_client).review("c", "too_many_products", {})

    assert review.verdict.is_actually_wrong
    assert review.review_feedback == "- 4 products listed\nHow to fix: Keep the best 3."


@pytest.mark.parametrize("output_text", ["", "not json", json.dumps({"is_actually_wrong": True})])
def test_invalid_verdict_raises(output_text):
    with pytest.raises(ResponseReviewError):
        ResponseReviewer(FakeReviewerClient(output_text)).review("c", "x", {})
