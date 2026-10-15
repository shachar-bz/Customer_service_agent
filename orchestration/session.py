"""Per-conversation state shared with the tools that need it (authenticate, price-aware tools)."""
from __future__ import annotations

from dataclasses import dataclass

from pricing.customer_pricing import PREMIER_DISCOUNT_RATE


@dataclass
class ConversationSession:
    is_premier: bool = False

    @property
    def discount_rate(self) -> float:
        return PREMIER_DISCOUNT_RATE if self.is_premier else 0.0
