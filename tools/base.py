"""Shared contract for agent tools: validate the LLM's arguments with pydantic, then call the tool function."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ValidationError


def execute_tool(
    tool_args_model: type[BaseModel],
    tool_function: Callable[..., dict[str, Any]],
    raw_args: dict[str, Any],
) -> dict[str, Any]:
    """tool_function arrives with its dependencies (data, session) already bound via functools.partial.
    Invalid arguments come back as an error the LLM can correct."""
    try:
        args = tool_args_model.model_validate(raw_args)
    except ValidationError as error:
        return {"error": f"Invalid arguments: {error}"}
    return tool_function(**args.model_dump())
