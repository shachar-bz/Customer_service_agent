"""authenticate tool: verifies a customer's email and password and records premier status in the session."""
from __future__ import annotations

from typing import Any

from mongomock.collection import Collection
from pydantic import BaseModel, ConfigDict, field_validator

from orchestration.session import ConversationSession

INVALID_CREDENTIALS_MESSAGE = "Invalid email or password."

AUTHENTICATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "authenticate",
        "description": (
            """Verify a customer's identity with their email and password.
                Returns the customer's full name and status (regular or premier).
                Call this whenever the customer provides their credentials."""
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Customer email address, e.g. rob.brown@email.net.",
                },
                "pw": {
                    "type": "string",
                    "description": "Customer password exactly as the customer wrote it.",
                },
            },
            "required": ["email", "pw"],
            "additionalProperties": False,
        },
    },
}


class AuthenticateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    pw: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        return email.strip().lower()


def authenticate(
    customers: Collection, session: ConversationSession, email: str, pw: str
) -> dict[str, Any]:
    customer = customers.find_one({"email": email, "pw": pw})
    if customer is None:
        # A failed attempt keeps any earlier successful login untouched.
        return {"error": INVALID_CREDENTIALS_MESSAGE}

    session.is_premier = customer["status"] == "premier"
    return {
        "full_name": f"{customer['first_name']} {customer['last_name']}",
        "status": customer["status"],
    }
