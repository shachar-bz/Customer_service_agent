"""Reviewer output format: the verdict model and its strict JSON schema for the Responses API."""
from __future__ import annotations

from pydantic import BaseModel

RESPONSE_REVIEW_FORMAT_NAME = "response_review"


class ResponseReviewVerdict(BaseModel):
    is_actually_wrong: bool
    problems: list[str]
    fix_instructions: str


RESPONSE_REVIEW_TEXT_FORMAT = {
    "type": "json_schema",
    "name": RESPONSE_REVIEW_FORMAT_NAME,
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "is_actually_wrong": {"type": "boolean"},
            "problems": {"type": "array", "items": {"type": "string"}},
            "fix_instructions": {"type": "string"},
        },
        "required": ["is_actually_wrong", "problems", "fix_instructions"],
        "additionalProperties": False,
    },
}
