"""QuestionOutcome: what one question produced, the agent run plus its response validation. Import-cheap, so the logger and entry point can use it."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from orchestration.agent import AgentRun

if TYPE_CHECKING:
    # The pipeline module transitively imports openai.
    from orchestration.response_validator.pipeline import ResponseValidation


@dataclass(frozen=True)
class QuestionOutcome:
    agent_run: AgentRun
    # None when validation did not run.
    response_validation: Optional[ResponseValidation]

    @property
    def final_answer(self) -> str:
        """The answer the customer gets."""
        return self.agent_run.final_answer
