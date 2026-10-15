"""get_customer tool: looks up a customer by email and/or full name and returns only their name and product interests."""
from __future__ import annotations

from typing import Any, Optional

from mongomock.collection import Collection
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

NO_CUSTOMER_FOUND_MESSAGE = "No customer found with the given email or name."
MISSING_LOOKUP_KEY_MESSAGE = "Provide at least one of email or name."
BLANK_VALUE_MESSAGE = "must not be blank"

GET_CUSTOMER_SCHEMA = {
    "type": "function",
    "name": "get_customer",
    "description": (
        """Look up a store customer by email or full name. Returns only the customer's full
            name and product interests (product categories they care about).
            Give at least one of email or name; if both are given, both must belong to the
            same customer.
            Use it to tailor recommendations, e.g. products matching the customer's own
            interests, or gift ideas for a friend who is a customer.
            The interests are private: use them to choose products, but do not list them
            back to anyone other than the authenticated customer themselves."""
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Customer email address, e.g. rob.brown@email.net.",
            },
            "name": {
                "type": "string",
                "description": "Customer's full name, first and last, e.g. 'Michelle Garcia'.",
            },
        },
        "additionalProperties": False,
    },
    "strict": False,
}


def normalize_full_name(full_name: str) -> str:
    """Collapse whitespace and lowercase so names compare case- and spacing-insensitively."""
    return " ".join(full_name.split()).lower()


class GetCustomerArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Optional[str] = None
    name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: Optional[str]) -> Optional[str]:
        if email is None:
            return None
        email = email.strip().lower()
        if not email:
            raise ValueError(BLANK_VALUE_MESSAGE)
        return email

    @field_validator("name")
    @classmethod
    def normalize_name(cls, name: Optional[str]) -> Optional[str]:
        if name is None:
            return None
        name = normalize_full_name(name)
        if not name:
            raise ValueError(BLANK_VALUE_MESSAGE)
        return name

    @model_validator(mode="after")
    def require_email_or_name(self) -> GetCustomerArgs:
        if self.email is None and self.name is None:
            raise ValueError(MISSING_LOOKUP_KEY_MESSAGE)
        return self


def get_customer(
    customers: Collection, email: Optional[str], name: Optional[str]
) -> dict[str, Any]:
    email_query = {} if email is None else {"email": email}
    for customer in customers.find(email_query):
        full_name = f"{customer['first_name']} {customer['last_name']}"
        if name is None or normalize_full_name(full_name) == name:
            # Callable without authentication (policy 4): expose only name and interests.
            return {
                "full_name": full_name,
                "product_interests": list(customer["product-interests"]),
            }
    return {"error": NO_CUSTOMER_FOUND_MESSAGE}
