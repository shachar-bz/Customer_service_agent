from orchestration.main_agent.agent import AgentRun
from orchestration.logger import format_question_outcome
from orchestration.question_outcome import QuestionOutcome
from orchestration.response_validator.fast_validator import FastValidationResult
from orchestration.response_validator.pipeline import validate_response
from orchestration.response_validator.reviewer import ResponseReview, ResponseReviewVerdict


class FakeFastValidator:
    def __init__(self, ok_probability=None, error=None):
        self._ok_probability = ok_probability
        self._error = error
        self.calls = 0

    def __call__(self, question, answer, products):
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

    def __call__(self, question, answer, flagged_label, probability_by_label):
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
    def __init__(self, repaired_answer="repaired", error=None):
        self._repaired_answer = repaired_answer
        self._error = error
        self.feedback = []

    def __call__(self, review_feedback):
        self.feedback.append(review_feedback)
        if self._error is not None:
            raise self._error
        return self._repaired_answer


def run_pipeline(fast_validator, reviewer, stopped_by_cap=False, repair_error=None):
    agent_run = AgentRun(question="q", final_answer="original", stopped_by_cap=stopped_by_cap)
    repair = RecordingRepair(error=repair_error)
    response_validation = validate_response(agent_run, fast_validator, reviewer, repair)
    return QuestionOutcome(agent_run=agent_run, response_validation=response_validation), repair


def test_ok_answer_is_returned_without_review():
    reviewer = FakeReviewer()

    question_outcome, repair = run_pipeline(FakeFastValidator(ok_probability=0.8), reviewer)

    assert question_outcome.final_answer == "original"
    assert reviewer.calls == [] and repair.feedback == []


def test_flagged_answer_that_reviewer_clears_is_kept():
    question_outcome, repair = run_pipeline(FakeFastValidator(ok_probability=0.2), FakeReviewer(is_actually_wrong=False))

    assert question_outcome.final_answer == "original"
    assert repair.feedback == []
    assert question_outcome.response_validation.review is not None


def test_confirmed_problem_is_repaired_once_with_review_feedback():
    reviewer = FakeReviewer(is_actually_wrong=True)

    question_outcome, repair = run_pipeline(FakeFastValidator(ok_probability=0.2), reviewer)

    assert reviewer.calls == ["too_many_products"]
    assert repair.feedback == ["- 4 products\nHow to fix: Keep 3."]
    assert question_outcome.final_answer == "repaired"
    assert question_outcome.response_validation.original_answer == "original"


def test_pipeline_leaves_agent_run_final_answer_untouched():
    question_outcome, _ = run_pipeline(FakeFastValidator(ok_probability=0.2), FakeReviewer())

    assert question_outcome.agent_run.final_answer == "original"
    assert question_outcome.response_validation.final_answer == "repaired"


def test_capped_run_is_not_validated():
    fast_validator = FakeFastValidator(ok_probability=0.0)

    question_outcome, _ = run_pipeline(fast_validator, FakeReviewer(), stopped_by_cap=True)

    assert fast_validator.calls == 0
    assert question_outcome.response_validation.fast_validation is None
    assert question_outcome.final_answer == "original"


def test_failures_keep_original_answer():
    cases = [
        (FakeFastValidator(error=RuntimeError("down")), FakeReviewer(), None),
        (FakeFastValidator(ok_probability=0.1), FakeReviewer(error=RuntimeError("down")), None),
        (FakeFastValidator(ok_probability=0.1), FakeReviewer(), RuntimeError("down")),
    ]
    for fast_validator, reviewer, repair_error in cases:
        question_outcome, _ = run_pipeline(fast_validator, reviewer, repair_error=repair_error)

        assert question_outcome.final_answer == "original"
        assert "down" in question_outcome.response_validation.error
        assert question_outcome.response_validation.original_answer is None


def test_log_includes_validation_and_original_answer():
    question_outcome, _ = run_pipeline(FakeFastValidator(ok_probability=0.2), FakeReviewer())

    log_text = format_question_outcome(question_outcome)

    assert "RESPONSE VALIDATION:" in log_text
    assert "ORIGINAL ANSWER: original" in log_text
    assert "FINAL ANSWER: repaired" in log_text
