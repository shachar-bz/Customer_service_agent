"""Per-conversation state (the premier flag) shared with the tools that need it: authenticate and price-aware tools. Lives in pricing/ so tools never import from orchestration/."""
from __future__ import annotations

from dataclasses import dataclass

from pricing.customer_pricing import PREMIER_DISCOUNT_RATE


@dataclass
class ConversationSession:
    is_premier: bool = False

    @property
    def discount_rate(self) -> float:
        return PREMIER_DISCOUNT_RATE if self.is_premier else 0.0
