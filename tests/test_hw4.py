import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_import_is_cheap():
    """The grader imports hw4 before any question: no data, index, or tool modules may load."""
    check = (
        "import sys; from hw4 import answer_question; "
        "heavy = [m for m in ('chromadb', 'openai', 'orchestration.runtime', 'tools') if m in sys.modules]; "
        "assert not heavy, heavy"
    )
    subprocess.run([sys.executable, "-c", check], cwd=PROJECT_ROOT, check=True)


def test_failure_returns_apology_instead_of_raising(monkeypatch):
    import orchestration.entrypoint
    import orchestration.logger
    import orchestration.runtime
    from hw4 import answer_question

    def failing_run(question):
        raise RuntimeError("no network")

    monkeypatch.setattr(orchestration.runtime, "run_customer_service_agent", failing_run)
    # Keeps this test's failure out of the real agent.log.
    monkeypatch.setattr(orchestration.logger.agent_logger, "handlers", [logging.NullHandler()])

    assert answer_question("anything") == orchestration.entrypoint.FAILURE_ANSWER


def test_success_returns_validated_answer_and_logs_outcome(monkeypatch):
    import orchestration.entrypoint
    import orchestration.runtime
    from hw4 import answer_question
    from orchestration.main_agent.agent import AgentRun
    from orchestration.question_outcome import QuestionOutcome
    from orchestration.response_validator.pipeline import ResponseValidation

    question_outcome = QuestionOutcome(
        agent_run=AgentRun(question="anything", final_answer="original"),
        response_validation=ResponseValidation(final_answer="repaired", original_answer="original"),
    )
    logged_outcomes = []
    monkeypatch.setattr(orchestration.runtime, "run_customer_service_agent", lambda question: question_outcome)
    monkeypatch.setattr(orchestration.entrypoint, "log_question_outcome", logged_outcomes.append)

    assert answer_question("anything") == "repaired"
    assert logged_outcomes == [question_outcome]
