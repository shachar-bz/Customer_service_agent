from types import SimpleNamespace

import pytest

from orchestration.response_validator.reviewer import (
    REVIEWER_MODEL,
    ResponseReviewError,
    ResponseReviewVerdict,
    review_response,
)


class FakeReviewerClient:
    def __init__(self, output_parsed):
        self._output_parsed = output_parsed
        self.requests = []
        self.responses = SimpleNamespace(parse=self._parse)

    def _parse(self, **request):
        self.requests.append(request)
        return SimpleNamespace(output_parsed=self._output_parsed)


def verdict(is_actually_wrong, problems=(), fix_instructions=""):
    return ResponseReviewVerdict(
        is_actually_wrong=is_actually_wrong, problems=list(problems), fix_instructions=fix_instructions
    )


def test_single_tool_free_call_with_context_and_flagged_label():
    reviewer_client = FakeReviewerClient(verdict(False))

    review = review_response(reviewer_client, "q", "a", "too_many_products", {"ok": 0.2}, ["Bikes"])

    [request] = reviewer_client.requests
    assert request["model"] == REVIEWER_MODEL
    assert "tools" not in request
    assert request["text_format"] is ResponseReviewVerdict
    assert "Customer message" in request["input"] and "too_many_products" in request["input"]
    assert "Customer product interests: Bikes" in request["input"]
    assert not review.verdict.is_actually_wrong


def test_wrong_verdict_becomes_review_feedback():
    reviewer_client = FakeReviewerClient(verdict(True, ["4 products listed"], "Keep the best 3."))

    review = review_response(reviewer_client, "q", "a", "too_many_products", {}, [])

    assert review.verdict.is_actually_wrong
    assert review.review_feedback == "- 4 products listed\nHow to fix: Keep the best 3."


def test_missing_parsed_verdict_raises():
    with pytest.raises(ResponseReviewError):
        review_response(FakeReviewerClient(None), "q", "a", "x", {}, [])
