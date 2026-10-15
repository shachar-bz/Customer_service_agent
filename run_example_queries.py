"""Runs the agent on example_queries.txt and prints each answer; per-run tool traces go to agent.log.

Usage: python run_example_queries.py            # all queries
       python run_example_queries.py q3 q10     # only the named ones
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from hw4 import answer_question

EXAMPLE_QUERIES_PATH = Path(__file__).resolve().parent / "example_queries.txt"
QUERY_LINE_PATTERN = re.compile(r"^(q\d+):\s*(.+)$")


def load_example_queries(queries_path: Path = EXAMPLE_QUERIES_PATH) -> dict[str, str]:
    """Maps query id (e.g. 'q3') to its question; '#' comment and blank lines are skipped."""
    example_queries = {}
    for line in queries_path.read_text(encoding="utf-8").splitlines():
        query_match = QUERY_LINE_PATTERN.match(line.strip())
        if query_match:
            example_queries[query_match.group(1)] = query_match.group(2).strip()
    return example_queries


def main(selected_query_ids: list[str]) -> None:
    example_queries = load_example_queries()
    unknown_query_ids = [query_id for query_id in selected_query_ids if query_id not in example_queries]
    if unknown_query_ids:
        sys.exit(f"Unknown query ids: {', '.join(unknown_query_ids)}")

    for query_id in selected_query_ids or list(example_queries):
        print(f"=== {query_id}: {example_queries[query_id]}")
        start_time = time.perf_counter()
        answer = answer_question(example_queries[query_id])
        print(f"--- answer ({time.perf_counter() - start_time:.1f}s):\n{answer}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
