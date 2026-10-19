from orchestration.agent import AgentRun
from orchestration.logger import format_agent_run
from orchestration.response_validator.fast_validator import FastValidationResult
from orchestration.response_validator.pipeline import SKIPPED_STOPPED_BY_CAP, ResponseValidationPipeline
from orchestration.response_validator.reviewer import ResponseReview, ResponseReviewVerdict


class FakeFastValidator:
    def __init__(self, ok_probability=None, error=None):
        self._ok_probability = ok_probability
        self._error = error
        self.calls = 0

    def validate(self, question, answer, products):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return FastValidationResult(
            {"ok": self._ok_probability, "too_many_products": 1 - self._ok_probability}, latency_ms=1.0
        )


class FakeReviewer:
    def __init__(self, is_actually_wrong=True, error=None):
        self._is_actually_wrong = is_actually_wrong
        self._error = error
        self.calls = []

    def review(self, response_context, flagged_label, probability_by_label):
        self.calls.append(flagged_label)
        if self._error is not None:
            raise self._error
        verdict = ResponseReviewVerdict(
            is_actually_wrong=self._is_actually_wrong,
            problems=["4 products"] if self._is_actually_wrong else [],
            fix_instructions="Keep 3." if self._is_actually_wrong else "",
        )
        return ResponseReview(verdict=verdict, latency_ms=1.0)


class RecordingRepair:
    def __init__(self, agent_run, repaired_answer="repaired", error=None):
        self._agent_run = agent_run
        self._repaired_answer = repaired_answer
        self._error = error
        self.feedback = []

    def __call__(self, review_feedback):
        self.feedback.append(review_feedback)
        self._agent_run.final_answer = "half-written"
        if self._error is not None:
            raise self._error
        self._agent_run.final_answer = self._repaired_answer


def run_pipeline(fast_validator, reviewer, stopped_by_cap=False, repair_error=None):
    agent_run = AgentRun(question="q", final_answer="original", stopped_by_cap=stopped_by_cap)
    repair = RecordingRepair(agent_run, error=repair_error)
    ResponseValidationPipeline(fast_validator, reviewer).validate(agent_run, repair)
    return agent_run, repair


def test_ok_answer_is_returned_without_review():
    reviewer = FakeReviewer()

    agent_run, repair = run_pipeline(FakeFastValidator(ok_probability=0.8), reviewer)

    assert agent_run.final_answer == "original"
    assert reviewer.calls == [] and repair.feedback == []


def test_flagged_answer_that_reviewer_clears_is_kept():
    agent_run, repair = run_pipeline(FakeFastValidator(ok_probability=0.2), FakeReviewer(is_actually_wrong=False))

    assert agent_run.final_answer == "original"
    assert repair.feedback == []
    assert agent_run.response_validation.review is not None


def test_confirmed_problem_is_repaired_once_with_review_feedback():
    reviewer = FakeReviewer(is_actually_wrong=True)

    agent_run, repair = run_pipeline(FakeFastValidator(ok_probability=0.2), reviewer)

    assert reviewer.calls == ["too_many_products"]
    assert repair.feedback == ["- 4 products\nHow to fix: Keep 3."]
    assert agent_run.final_answer == "repaired"
    assert agent_run.response_validation.original_answer == "original"


def test_capped_run_is_not_validated():
    fast_validator = FakeFastValidator(ok_probability=0.0)

    agent_run, _ = run_pipeline(fast_validator, FakeReviewer(), stopped_by_cap=True)

    assert fast_validator.calls == 0
    assert agent_run.response_validation.skipped_reason == SKIPPED_STOPPED_BY_CAP


def test_failures_keep_original_answer():
    cases = [
        (FakeFastValidator(error=RuntimeError("down")), FakeReviewer(), None),
        (FakeFastValidator(ok_probability=0.1), FakeReviewer(error=RuntimeError("down")), None),
        (FakeFastValidator(ok_probability=0.1), FakeReviewer(), RuntimeError("down")),
    ]
    for fast_validator, reviewer, repair_error in cases:
        agent_run, _ = run_pipeline(fast_validator, reviewer, repair_error=repair_error)

        assert agent_run.final_answer == "original"
        assert "down" in agent_run.response_validation.error
        assert agent_run.response_validation.original_answer is None


def test_log_includes_validation_and_original_answer():
    agent_run, _ = run_pipeline(FakeFastValidator(ok_probability=0.2), FakeReviewer())

    log_text = format_agent_run(agent_run)

    assert "RESPONSE VALIDATION:" in log_text
    assert "ORIGINAL ANSWER: original" in log_text
    assert "FINAL ANSWER: repaired" in log_text
