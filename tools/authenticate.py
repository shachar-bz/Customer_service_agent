"""authenticate tool: verifies a customer's email and password and records premier status in the session."""
from __future__ import annotations

from typing import Any

from mongomock.collection import Collection
from pydantic import BaseModel, ConfigDict, field_validator

from orchestration.session import ConversationSession
from tools.base import Tool

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


class AuthenticateTool(Tool):
    SCHEMA = AUTHENTICATE_SCHEMA
    ArgsModel = AuthenticateArgs

    def __init__(self, customers: Collection, session: ConversationSession):
        self.customers = customers
        self.session = session

    def run(self, args: AuthenticateArgs) -> dict[str, Any]:
        customer = self.customers.find_one({"email": args.email, "pw": args.pw})
        if customer is None:
            # A failed attempt keeps any earlier successful login untouched.
            return {"error": INVALID_CREDENTIALS_MESSAGE}

        self.session.is_premier = customer["status"] == "premier"
        return {
            "full_name": f"{customer['first_name']} {customer['last_name']}",
            "status": customer["status"],
        }
