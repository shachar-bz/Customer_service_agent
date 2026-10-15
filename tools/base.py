"""Abstract contract every agent tool implements: a schema for the LLM, pydantic validation, and run."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError


class Tool(ABC):
    SCHEMA: ClassVar[dict[str, Any]]
    ArgsModel: ClassVar[type[BaseModel]]

    @property
    def name(self) -> str:
        return self.SCHEMA["function"]["name"]

    def execute(self, raw_args: dict[str, Any]) -> dict[str, Any]:
        """Validates the LLM's arguments; invalid ones come back as an error the LLM can correct."""
        try:
            args = self.ArgsModel.model_validate(raw_args)
        except ValidationError as error:
            return {"error": f"Invalid arguments for {self.name}: {error}"}
        return self.run(args)

    @abstractmethod
    def run(self, args: BaseModel) -> dict[str, Any]:
        ...
