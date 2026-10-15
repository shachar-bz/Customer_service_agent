import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_import_is_cheap():
    """The grader imports hw4 before any question: no data, index, or tool modules may load."""
    check = (
        "import sys, hw4; "
        "heavy = [m for m in ('chromadb', 'openai', 'orchestration.runtime', 'tools') if m in sys.modules]; "
        "assert not heavy, heavy"
    )
    subprocess.run([sys.executable, "-c", check], cwd=PROJECT_ROOT, check=True)


def test_failure_returns_apology_instead_of_raising(monkeypatch):
    import hw4
    import orchestration.runtime

    def failing_run(question):
        raise RuntimeError("no network")

    monkeypatch.setattr(orchestration.runtime, "run_customer_service_agent", failing_run)

    assert hw4.answer_question("anything") == hw4.FAILURE_ANSWER
