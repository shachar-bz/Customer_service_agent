"""Assignment entry point: exposes answer_question(question) -> str from the customer-service agent.

Import-safe: data, vector index and clients load lazily on the first call.
"""
from __future__ import annotations

from orchestration.agent import answer_question

__all__ = ["answer_question"]

if __name__ == "__main__":
    import sys

    print(answer_question(" ".join(sys.argv[1:]) or input("Question: ")))
