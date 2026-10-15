# 1. Conversation session holds only the premier flag

## Context
Premier customers get a 5% discount. Price-aware tools (e.g. a hard-constraint price filter) must apply it, because an item listed at $104.99 still fits a $100 budget for a premier customer. The LLM should not be trusted to claim a discount or do the price math.

## Decision
- `orchestration/session.py` defines `ConversationSession`, one instance per conversation, holding only `is_premier`. `discount_rate` is derived from it.
- `authenticate` sets `is_premier` on success. A failed attempt returns "Invalid email or password." for both unknown email and wrong password, and leaves the session unchanged. A later successful login replaces it.
- The session is injected through `__init__` only into tools that need it (authenticate, price-aware tools). Other tools never see it.
- Pricing rules live in `pricing/customer_pricing.py`; every price-aware tool returns the shared priced product view, so the agent gets list, sale and customer price without doing arithmetic.
- No password, interests or identity are stored in the session.

## Consequences
- The session cannot tell a logged-in regular customer from an anonymous one. Tools that must gate customer data (policy 4) verify email and password themselves.
- `tools/` depends on `orchestration/session.py`; that module must not import from `tools/` to avoid a cycle.
